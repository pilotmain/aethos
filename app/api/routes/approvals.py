"""
Phase 70 — Mission Control "Pending Approvals" panel API.

Surfaces existing :class:`~app.models.agent_job.AgentJob` rows that are flagged
``awaiting_approval=True`` (Phase 38 approval gate) so the web UI can list and
approve / deny them. Approve / deny still flows through the existing
``POST /api/v1/jobs/{id}/decision`` endpoint (this module is read-only by design
to avoid splitting the source of truth with the legacy Telegram approval queue).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_current_user_id
from app.models.agent_job import AgentJob
from app.services.execution_policy import assess_interaction_risk
from app.services.user_capabilities import is_privileged_owner_for_web_mutations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["approvals"])


# ---------------------------------------------------------------------------
# Phase 76 — Blue-Green safety simulation (read-only "would do …" preview)
# ---------------------------------------------------------------------------


def _ensure_simulation_enabled() -> None:
    settings = get_settings()
    if not bool(getattr(settings, "nexa_simulation_enabled", True)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Simulation is disabled "
                "(set NEXA_SIMULATION_ENABLED=1 to enable Blue-Green preview)."
            ),
        )


def _require_owner(db: Session, app_user_id: str) -> None:
    if not is_privileged_owner_for_web_mutations(db, app_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Simulation requires an owner: Telegram-linked owner, governance "
                "owner/admin, or organization owner/admin."
            ),
        )


class SimulatePayloadBody(BaseModel):
    payload: dict[str, Any] = Field(
        ...,
        description=(
            "Host executor payload to simulate. Same shape as a real job payload "
            "(e.g. {'host_action': 'file_write', 'relative_path': '...', 'content': '...'})."
        ),
    )


def _simulate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Run validation + permission gates via execute_payload(simulate=True), then
    build the structured plan. Returns ``{ok, plan_text, structured_plan, error}``.

    The plan_text comes straight from the existing host_executor simulator
    (so the operator sees exactly what the legacy ``[SIMULATED]`` output
    would have shown). The structured_plan is the Phase 76 JSON shape
    (per-action fields + optional file_write diff).
    """
    from app.services.host_executor import build_simulation_plan, execute_payload

    out: dict[str, Any] = {
        "ok": False,
        "plan_text": "",
        "structured_plan": None,
        "error": None,
    }
    try:
        out["plan_text"] = execute_payload(payload, simulate=True)
        out["ok"] = True
    except ValueError as exc:
        out["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("simulation execute_payload failed: %s", exc, exc_info=True)
        out["error"] = f"simulation_failed: {exc!s}"
    try:
        out["structured_plan"] = build_simulation_plan(payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("build_simulation_plan failed: %s", exc, exc_info=True)
        out["structured_plan"] = {
            "action": "(error)",
            "kind": "unknown",
            "fields": {"error": f"plan_build_failed: {exc!s}"[:200]},
            "diff": None,
            "steps": None,
            "supports_diff": False,
        }
    return out


@router.post("/-/simulate-payload")
def simulate_arbitrary_payload(
    body: SimulatePayloadBody = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """
    Phase 76 — owner-gated preview for an arbitrary host executor payload.

    Used by the Telegram /simulate handler and by the web modal when the
    caller wants to preview a payload that isn't tied to an existing
    pending agent_job (e.g. dry-run of a planned action). Nothing is
    executed; the same validation + permission gates as a real run still
    apply.
    """
    _ensure_simulation_enabled()
    _require_owner(db, user_id)
    return _simulate_payload(body.payload)


@router.get("/{job_id}/simulate")
@router.post("/{job_id}/simulate")
def simulate_pending_approval(
    job_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """
    Phase 76 — owner-gated preview for an existing pending agent_job.

    Looks up the job by id (must belong to the caller and currently be
    awaiting approval), then runs ``execute_payload(simulate=True)`` and
    builds the structured plan from ``job.payload_json``.

    The endpoint is read-only — approve / deny still flows through the
    existing ``POST /api/v1/web/jobs/{id}/decision`` proxy. The UI uses
    this endpoint to render the "Simulate" modal and then calls the
    decision endpoint when the operator clicks "Approve & Execute".
    """
    _ensure_simulation_enabled()
    _require_owner(db, user_id)

    job = db.get(AgentJob, job_id)
    if job is None or str(job.user_id) != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"agent_job #{job_id} not found for current user",
        )
    if not bool(job.awaiting_approval):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"agent_job #{job_id} is not awaiting approval "
                f"(status={job.status!r}); refusing to simulate."
            ),
        )

    payload = job.payload_json or {}
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"agent_job #{job_id} has no structured payload to simulate.",
        )

    result = _simulate_payload(payload)
    result["job_id"] = job_id
    result["title"] = job.title or "Pending action"
    result["risk_level"] = job.risk_level
    try:
        job.simulation_result = result
        db.add(job)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not persist simulation_result for job %s: %s", job_id, exc)
        db.rollback()
    return result


@router.get("/-/capabilities")
def simulation_capabilities(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Phase 76 — expose simulation gating + caps so the UI can render a banner."""
    settings = get_settings()
    return {
        "simulation_enabled": bool(getattr(settings, "nexa_simulation_enabled", True)),
        "max_diff_lines": int(getattr(settings, "nexa_simulation_max_diff_lines", 500)),
        "is_owner": is_privileged_owner_for_web_mutations(db, user_id),
        "panel_enabled": bool(getattr(settings, "nexa_approvals_panel_enabled", True)),
    }


def _job_to_pending_row(job: AgentJob) -> dict[str, Any]:
    """Return the minimal payload the web panel needs to render one approval card."""
    payload = job.payload_json or {}
    payload_safe = payload if isinstance(payload, dict) else {}
    host_action = (payload_safe.get("host_action") or payload_safe.get("action") or "").strip().lower() or None
    target = (
        payload_safe.get("provider")
        or payload_safe.get("target")
        or payload_safe.get("repo")
        or payload_safe.get("workspace")
        or None
    )
    description_source = (job.instruction or job.title or "").strip()
    description = description_source[:500] if description_source else ""

    return {
        "id": job.id,
        "title": job.title or "Pending action",
        "description": description,
        "kind": job.kind,
        "worker_type": job.worker_type,
        "command_type": job.command_type,
        "host_action": host_action,
        "target": target,
        "risk_level": job.risk_level,
        "status": job.status,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "approval_decision": job.approval_decision,
        "approval_context": job.approval_context_json,
        "payload_preview": _payload_preview(payload_safe),
    }


def _payload_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip large / sensitive fields before sending to the browser."""
    if not isinstance(payload, dict):
        return {}
    preview: dict[str, Any] = {}
    for key in (
        "host_action",
        "action",
        "command",
        "argv",
        "ref",
        "remote",
        "branch",
        "service",
        "environment",
        "cwd_relative",
        "files",
        "repo",
        "workspace",
        "provider",
        "skill",
        "actions",
    ):
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, str) and len(value) > 500:
            preview[key] = value[:497] + "…"
        elif isinstance(value, (list, dict)):
            try:
                import json

                serialized = json.dumps(value, default=str)
            except (TypeError, ValueError):
                serialized = str(value)
            if len(serialized) > 1500:
                preview[key] = serialized[:1497] + "…"
            else:
                preview[key] = value
        else:
            preview[key] = value
    return preview


@router.get("/pending")
def list_pending_approvals(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    limit: int = 50,
) -> dict[str, Any]:
    """
    Return ``agent_jobs`` rows where ``awaiting_approval=True`` for the caller.

    The companion approve / deny endpoints already exist at
    ``POST /api/v1/jobs/{id}/decision`` (payload ``{"decision": "approved" | "denied"}``);
    this endpoint deliberately does **not** mutate state.
    """
    settings = get_settings()
    if not bool(getattr(settings, "nexa_approvals_panel_enabled", True)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Approvals panel disabled (set NEXA_APPROVALS_PANEL_ENABLED=1 to enable).",
        )

    safe_limit = max(1, min(int(limit or 0) or 50, 200))
    stmt = (
        select(AgentJob)
        .where(AgentJob.user_id == user_id)
        .where(AgentJob.awaiting_approval.is_(True))
        .order_by(AgentJob.created_at.desc())
        .limit(safe_limit)
    )
    rows = list(db.scalars(stmt).all())
    return {
        "approvals": [_job_to_pending_row(job) for job in rows],
        "count": len(rows),
        "limit": safe_limit,
    }


@router.get("/risk-preview")
def preview_action_risk(text: str = "") -> dict[str, Any]:
    """
    Lightweight helper so the UI / agents can ask "what risk tier would this be?"
    without having to wire up the full host_executor pipeline. Wraps
    :func:`app.services.execution_policy.assess_interaction_risk`.
    """
    tier = assess_interaction_risk(text)
    return {"risk": tier, "text_preview": (text or "")[:200]}
