"""Orchestrator hook: run development assignments via Cursor Cloud Agents when enabled."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.agent_team import AgentAssignment
from app.services.audit_service import audit
from app.services.cursor_integration.cursor_client import (
    CursorApiError,
    CursorCloudClient,
    dig,
    failed_run_status,
    parse_create_agent_response,
    parse_run_status,
    terminal_run_status,
)
from app.services.cursor_integration.cursor_events import (
    CURSOR_RUN_COMPLETED,
    CURSOR_RUN_CREATED,
    CURSOR_RUN_FAILED,
    CURSOR_RUN_STARTED,
)
from app.services.governance.policies import get_effective_policy, validate_cursor_run_against_policy

logger = logging.getLogger(__name__)


def _repo_allowed(repo_url: str) -> bool:
    s = get_settings()
    raw = (s.cursor_allowed_repo_urls or "").strip()
    if not raw:
        return True
    allowed = [x.strip() for x in raw.split(",") if x.strip()]
    ru = (repo_url or "").strip().rstrip("/")
    return any(ru.startswith(prefix.rstrip("/")) for prefix in allowed)


def try_cursor_dispatch(db: Session, *, row: AgentAssignment, uid: str) -> dict[str, Any] | None:
    """
    If this assignment should execute on Cursor Cloud, run it and return a **terminal** dispatch dict.

    Returns None to continue with custom-agent / orchestrator paths.
    """
    s = get_settings()
    if not s.cursor_enabled:
        return None
    ij = row.input_json or {}
    k = (ij.get("kind") or "").strip().lower()
    tt = (ij.get("task_type") or "").strip().lower()
    if k != "development" and tt != "development":
        return None
    if not (s.cursor_api_key or "").strip():
        logger.info("Cursor enabled but CURSOR_API_KEY missing; falling back to custom agent.")
        return None

    repo_url = (s.cursor_default_repo_url or "").strip()
    branch = (s.cursor_default_branch or "main").strip() or "main"
    if not repo_url:
        _fail_assignment(
            db,
            row=row,
            uid=uid,
            err="Set CURSOR_DEFAULT_REPO_URL to a GitHub repository URL to run Cloud Agents.",
        )
        return {"ok": False, "error": row.error, "assignment_id": row.id}

    if not _repo_allowed(repo_url):
        _fail_assignment(
            db,
            row=row,
            uid=uid,
            err=f"Repository is not allowed by CURSOR_ALLOWED_REPO_URLS: {repo_url}",
        )
        return {"ok": False, "error": row.error, "assignment_id": row.id}

    if s.nexa_governance_enabled:
        oid = (s.nexa_default_organization_id or "").strip()[:64]
        if oid:
            pol = get_effective_policy(db, organization_id=oid)
            ok_pol, denied_msg = validate_cursor_run_against_policy(
                policy=pol, repo_url=repo_url, branch=branch
            )
            if not ok_pol:
                audit(
                    db,
                    event_type="cursor.run.denied_by_policy",
                    actor="governance",
                    user_id=uid,
                    message=f"Assignment #{row.id}: {denied_msg}",
                    metadata={"assignment_id": row.id, "repo": repo_url, "branch": branch},
                    organization_id=oid,
                )
                _fail_assignment(
                    db,
                    row=row,
                    uid=uid,
                    err=denied_msg or "Denied by organization policy.",
                )
                return {"ok": False, "error": row.error, "assignment_id": row.id}

    body = (ij.get("user_message") or row.description or "").strip()
    if not body:
        _fail_assignment(db, row=row, uid=uid, err="Assignment has no instruction text for Cursor.")
        return {"ok": False, "error": row.error, "assignment_id": row.id}

    model_id = (s.cursor_default_model or "").strip() or None
    client = CursorCloudClient(
        api_key=s.cursor_api_key,
        base_url=s.cursor_api_base,
        timeout_seconds=float(s.cursor_http_timeout_seconds),
    )

    try:
        raw_create = client.create_agent_run(
            prompt_text=body[:120_000],
            repo_url=repo_url,
            starting_ref=branch,
            model_id=model_id,
            auto_create_pr=bool(s.cursor_auto_create_pr),
        )
    except CursorApiError as exc:
        logger.error("Cursor create_agent_run failed (HTTP): %s", exc)
        _fail_assignment(
            db,
            row=row,
            uid=uid,
            err=str(exc),
            metadata_extra={"cursor_phase": "create_agent_run", "http_status": exc.status_code},
        )
        return {"ok": False, "error": row.error, "assignment_id": row.id}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Cursor create_agent_run failed: %s", exc)
        _fail_assignment(
            db,
            row=row,
            uid=uid,
            err=f"Cursor API error: {exc}",
            metadata_extra={"cursor_phase": "create_agent_run"},
        )
        return {"ok": False, "error": row.error, "assignment_id": row.id}

    agent_id, run_id, _ = parse_create_agent_response(raw_create)

    if not agent_id or not run_id:
        _fail_assignment(
            db,
            row=row,
            uid=uid,
            err="Cursor API response missing agent or run id.",
        )
        audit(
            db,
            event_type=CURSOR_RUN_FAILED,
            actor="aethos",
            user_id=uid,
            message=f"Cursor parse failed for assignment #{row.id}",
            metadata={"assignment_id": row.id},
        )
        return {"ok": False, "error": row.error, "assignment_id": row.id}

    row.status = "running"
    row.started_at = row.started_at or datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)

    audit(
        db,
        event_type=CURSOR_RUN_STARTED,
        actor="aethos",
        user_id=uid,
        message=f"Cursor run started for assignment #{row.id}",
        metadata={
            "assignment_id": row.id,
            "cursor_agent_id": agent_id,
            "cursor_run_id": run_id,
            "repo": repo_url,
            "branch": branch,
        },
    )
    audit(
        db,
        event_type=CURSOR_RUN_CREATED,
        actor="aethos",
        user_id=uid,
        message=f"Cursor agent/run created for assignment #{row.id}",
        metadata={
            "assignment_id": row.id,
            "cursor_agent_id": agent_id,
            "cursor_run_id": run_id,
            "repo": repo_url,
            "branch": branch,
        },
    )

    # Poll run until terminal (best-effort; API shape may vary).
    status = "UNKNOWN"
    iterations = max(1, int(s.cursor_max_poll_iterations))
    interval = max(0.5, float(s.cursor_poll_interval_seconds))
    last_payload: dict[str, Any] | None = None
    for _ in range(iterations):
        try:
            last_payload = client.get_run(agent_id=agent_id, run_id=run_id)
            status = parse_run_status(last_payload)
            if terminal_run_status(status):
                break
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cursor get_run poll error: %s", exc)
        time.sleep(interval)

    ok_run = not failed_run_status(status)
    completed_audit = CURSOR_RUN_COMPLETED if ok_run else CURSOR_RUN_FAILED

    cursor_block = {
        "cursor_run_id": run_id,
        "cursor_agent_id": agent_id,
        "cursor_status": status,
        "cursor_repo": repo_url,
        "cursor_branch": branch,
        "cursor_cost_estimate": (
            (dig(last_payload, "costEstimate") or dig(last_payload, "cost")) if last_payload else None
        ),
    }

    summary_text = (
        f"Cursor Cloud Agent finished with status **{status}**.\n"
        f"- Repo: `{repo_url}` @ `{branch}`\n"
        f"- Agent: `{agent_id}` · Run: `{run_id}`"
    )

    row.status = "completed" if ok_run else "failed"
    row.completed_at = datetime.utcnow()
    row.error = None if ok_run else (f"Cursor run status: {status}")[:8000]
    row.output_json = {
        "text": summary_text,
        "kind": "cursor_cloud_agent",
        "cursor": cursor_block,
        "cursor_raw_run": last_payload,
    }
    db.add(row)
    db.commit()

    audit(
        db,
        event_type=completed_audit,
        actor="aethos",
        user_id=uid,
        message=f"Cursor run {status} for assignment #{row.id}",
        metadata={
            "assignment_id": row.id,
            **cursor_block,
        },
    )

    return {"ok": ok_run, "assignment_id": row.id, "output": row.output_json}


def _fail_assignment(
    db: Session,
    *,
    row: AgentAssignment,
    uid: str,
    err: str,
    metadata_extra: dict[str, Any] | None = None,
) -> None:
    row.status = "failed"
    row.completed_at = datetime.utcnow()
    row.error = (err or "")[:8000]
    db.add(row)
    db.commit()
    md: dict[str, Any] = {"assignment_id": row.id, "error": row.error[:2000]}
    if metadata_extra:
        md.update(metadata_extra)
    audit(
        db,
        event_type=CURSOR_RUN_FAILED,
        actor="aethos",
        user_id=uid,
        message=f"Assignment #{row.id} failed (Cursor)",
        metadata=md,
    )
