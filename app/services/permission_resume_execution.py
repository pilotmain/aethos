"""Approve-time resume: re-run enforcement, then enqueue the pending host_executor job."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.access_permission import AccessPermission
from app.models.agent_team import AgentAssignment
from app.services.audit_service import audit
from app.services.content_provenance import InstructionSource, normalize_instruction_source
from app.services.enforcement_pipeline import ExecutionContext, enforce_host_execution_policy
from app.services.host_executor_chat import (
    enqueue_host_job_from_validated_payload,
    _validate_enqueue_payload,
)
from app.services.permission_request_flow import precheck_host_executor_permissions
from app.services.trust_audit_constants import ACCESS_HOST_EXECUTOR_BLOCKED, HOST_EXECUTION_ALLOWED


logger = logging.getLogger(__name__)


def _coerce_positive_int(value: Any) -> int | None:
    if isinstance(value, int) and value > 0:
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        v = int(value.strip())
        return v if v > 0 else None
    return None


def _ensure_valid_directory_base(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize ``read_multiple_files`` so ``base`` is the single canonical directory (no drift).

    **Case A — ``nexa_permission_abs_targets`` present** (outside-root / permissioned path)::

        payload["base"] = Path(abs_targets[0]).expanduser().resolve()
        (must exist, be a directory, or :class:`PermissionResumeError`).

    **Case B — no abs targets** (inside work root)::

        payload["base"] = (host_executor_work_root / relative_path).resolve()
    """
    out = dict(payload)
    if (out.get("host_action") or "").strip().lower() != "read_multiple_files":
        return out
    raw = out.get("nexa_permission_abs_targets")
    if isinstance(raw, list) and raw and str(raw[0]).strip():
        try:
            base = Path(str(raw[0]).strip()).expanduser().resolve()
        except OSError as e:
            raise PermissionResumeError(f"Invalid base path: {e}") from e
        if not base.exists():
            raise PermissionResumeError(f"Base path does not exist: {base}")
        if not base.is_dir():
            raise PermissionResumeError(f"Base path must be a directory: {base}")
        out["base"] = str(base)
        return out
    rel = str(out.get("relative_path") or out.get("relative_dir") or ".").strip() or "."
    try:
        root = Path(get_settings().host_executor_work_root).expanduser().resolve()
        out["base"] = str((root / rel.replace("\\", "/")).resolve())
    except OSError as e:
        raise PermissionResumeError(f"Invalid base path: {e}") from e
    return out


class PermissionResumeError(RuntimeError):
    """User-safe error surfaced when approve cannot enqueue (policy, grants, validation)."""


def _strip_pending_resume_metadata(db: Session, row: AccessPermission) -> None:
    md = dict(row.metadata_json or {})
    md.pop("pending_payload", None)
    md.pop("pending_title", None)
    row.metadata_json = md
    db.add(row)
    db.commit()


def resume_host_executor_after_grant(
    db: Session,
    owner_user_id: str,
    permission_id: int,
    *,
    web_session_id: str | None = None,
) -> int:
    """
    After grant_permission succeeds, load pending_payload, re-enforce policy + DB checks, enqueue job.

    Clears pending_payload from the permission row metadata when enqueue succeeds.

    Returns (job_id, permission_required_echo_dict_for_tests).
    """
    row = db.get(AccessPermission, int(permission_id))
    if not row or row.owner_user_id != (owner_user_id or "").strip()[:64]:
        raise PermissionResumeError("Permission not found.")

    md = dict(row.metadata_json or {})
    pending_raw = md.get("pending_payload")
    title = str(md.get("pending_title") or "Host action").strip() or "Host action"

    if not isinstance(pending_raw, dict):
        raise PermissionResumeError(
            "No pending action stored for this permission — ask Nexa again for what you wanted to run."
        )

    uid = str(owner_user_id).strip()

    trusted = pending_raw.get("instruction_source") or InstructionSource.USER_MESSAGE.value
    trusted_norm = normalize_instruction_source(str(trusted))
    ctx = ExecutionContext(
        db=db,
        user_id=uid,
        trusted_instruction_source=trusted_norm,
        boundary="host_resume",
    )
    enforced = enforce_host_execution_policy(pending_raw, ctx=ctx)
    enforced = _ensure_valid_directory_base(enforced)

    ok_pre, err_pre = precheck_host_executor_permissions(db, uid, enforced)
    if not ok_pre:
        audit(
            db,
            event_type=ACCESS_HOST_EXECUTOR_BLOCKED,
            actor="system",
            user_id=uid,
            message=(err_pre or "resume blocked")[:2000],
            metadata={
                "permission_id": permission_id,
                "phase": "resume_after_grant",
            },
        )
        raise PermissionResumeError((err_pre or "That action is not allowed.").strip()[:2500])

    safe_pl = _validate_enqueue_payload(enforced)
    if not safe_pl:
        audit(
            db,
            event_type=ACCESS_HOST_EXECUTOR_BLOCKED,
            actor="system",
            user_id=uid,
            message="resume validation failed",
            metadata={"permission_id": permission_id, "phase": "resume_validate"},
        )
        raise PermissionResumeError(
            "That host action cannot be resumed anymore — ask Nexa again with a supported request."
        )

    if not getattr(get_settings(), "nexa_host_executor_enabled", False):
        raise PermissionResumeError(
            "Host execution is disabled (`NEXA_HOST_EXECUTOR_ENABLED`). Enable it on the API host."
        )

    ws = (web_session_id or md.get("web_session_id") or "default").strip()[:64] or "default"
    row_scope = str(getattr(row, "scope", "") or "")[:64] or None
    row_target = str(getattr(row, "target", "") or "")[:8000] or None
    # Assignment linkage: pending_payload (host bridge stamps agent_assignment_id) and/or
    # permission metadata (assignment_id / agent_assignment_id from request_permission_from_chat).
    assign_id = _coerce_positive_int(pending_raw.get("agent_assignment_id"))
    if assign_id is None:
        assign_id = _coerce_positive_int(md.get("assignment_id"))
    if assign_id is None:
        assign_id = _coerce_positive_int(md.get("agent_assignment_id"))

    # Host execution resumes from the stamped pending_payload (same hash as approve UI).
    # We do not call dispatch_assignment() here: that would re-infer from user text and could
    # diverge or double-enqueue; enqueue + assignment update is the single resume path.

    job = enqueue_host_job_from_validated_payload(
        db,
        uid,
        safe_pl=safe_pl,
        title=title,
        web_session_id=ws,
        access_permission_resume=True,
        permission_request_id=int(permission_id),
        permission_scope=row_scope,
        permission_target=row_target,
        agent_assignment_id=assign_id,
    )

    _strip_pending_resume_metadata(db, row)

    if assign_id is not None:
        arow = db.get(AgentAssignment, int(assign_id))
        if arow and arow.user_id == uid:
            arow.status = "running"
            arow.started_at = arow.started_at or datetime.utcnow()
            inp = dict(arow.input_json or {})
            inp.pop("pending_permission_id", None)
            arow.input_json = inp
            arow.output_json = {
                "host_job_id": job.id,
                "kind": "host_executor_queued",
                "note": "Host job queued after permission approval.",
            }
            arow.error = None
            db.add(arow)
            db.commit()
            audit(
                db,
                event_type="agent_assignment.dispatched",
                actor="user",
                user_id=uid,
                message=f"Assignment #{arow.id} resumed after grant → host job #{job.id}",
                metadata={
                    "assignment_id": arow.id,
                    "host_job_id": job.id,
                    "permission_id": permission_id,
                },
            )

    audit(
        db,
        event_type=HOST_EXECUTION_ALLOWED,
        actor="user",
        user_id=uid,
        message=f"resume_after_grant permission_id={permission_id} job_id={job.id}",
        metadata={
            "permission_id": permission_id,
            "job_id": job.id,
            "host_action": safe_pl.get("host_action"),
            "assignment_id": assign_id,
        },
    )

    return int(job.id)


def peek_pending_payload(db: Session, owner_user_id: str, permission_id: int) -> dict[str, Any]:
    """Return pending_payload blob for diagnostics/tests (does not enqueue)."""
    row = db.get(AccessPermission, int(permission_id))
    if not row or row.owner_user_id != owner_user_id[:64]:
        raise PermissionResumeError("Permission not found.")
    md = dict(row.metadata_json or {})
    pl = md.get("pending_payload")
    if not isinstance(pl, dict):
        raise PermissionResumeError("No pending payload.")
    return pl
