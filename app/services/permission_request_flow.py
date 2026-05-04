"""Chat-first permission requests for host enqueue (aligned Web + Telegram copy)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.access_permission import AccessPermission
from app.services.access_permissions import (
    STATUS_DENIED,
    STATUS_PENDING,
    check_host_executor_job,
    format_awaiting_permission_duplicate,
    format_permission_request_prompt,
    host_action_scope_and_risk,
    reason_for_scope,
    request_permission,
    resolve_host_executor_permission_paths,
)
from app.services.workspace_registry import default_work_root_path


def validate_host_payload_paths_before_permission(payload: dict[str, Any]) -> tuple[bool, str | None]:
    """
    For host payloads that reference absolute paths, ensure targets exist before showing a permission card.
    Returns (ok, user_safe_error_or_none).
    """
    ha = (payload.get("host_action") or "").strip().lower()
    if ha != "read_multiple_files":
        return True, None
    raw = payload.get("nexa_permission_abs_targets")
    if not isinstance(raw, list) or not raw:
        return True, None
    try:
        p0 = Path(str(raw[0]).strip()).expanduser().resolve()
    except OSError as e:
        return False, f"Invalid path: {e}"
    if not p0.exists():
        return False, f"Path does not exist: {p0}"
    if not p0.is_dir():
        return False, f"Expected a directory for folder reads: {p0}"
    return True, None


def is_missing_grant_error(message: str) -> bool:
    return "no granted permission" in (message or "").lower()


def is_permission_eligible_precheck_failure(message: str, payload: dict[str, Any]) -> bool:
    """
    True when we should show the permission-request card instead of a hard denial.

    Explicit absolute targets (``nexa_permission_abs_targets``) may fail workspace policy
    before grant resolution; those cases must still route to approve-and-run.
    """
    if is_missing_grant_error(message):
        return True
    raw_abs = payload.get("nexa_permission_abs_targets")
    if not isinstance(raw_abs, list) or not raw_abs:
        return False
    em = (message or "").lower()
    return bool(
        any(
            phrase in em
            for phrase in (
                "path outside registered workspace roots",
                "path outside default work root",
                "no workspace roots registered",
                "outside registered workspace",
            )
        )
    )


def still_waiting_permission_message() -> str:
    return "🔐 **Permission required**\n\nStill awaiting approval for this action."


def find_pending_permission_duplicate(
    db: Session,
    owner_user_id: str,
    *,
    scope: str,
    target: str,
) -> AccessPermission | None:
    st = (
        select(AccessPermission)
        .where(
            AccessPermission.owner_user_id == owner_user_id[:64],
            AccessPermission.scope == scope[:64],
            AccessPermission.status == STATUS_PENDING,
            AccessPermission.target == (target or "")[:8000],
        )
        .limit(1)
    )
    return db.scalars(st).first()


def derive_permission_reason(scope: str, *, reason_override: str | None = None) -> str:
    r = (reason_override or "").strip()
    return r if r else reason_for_scope(scope)


def reason_for_host_payload(payload: dict[str, Any]) -> str:
    """Human reason line for permission cards (stable, not LLM-derived)."""
    ha = (payload.get("host_action") or "").strip().lower()
    if ha == "list_directory":
        return "List directory contents"
    if ha == "find_files":
        return "Search files in this folder"
    if ha == "file_read":
        return "Read file contents"
    if ha == "file_write":
        return "Write file on disk"
    if ha in ("read_multiple_files",):
        return "Read and analyze local files"
    if ha == "git_status":
        return "Show git status"
    if ha == "git_commit":
        return "Create a git commit"
    if ha == "git_push":
        return "Push commits to the remote"
    if ha == "run_command":
        rn = (payload.get("run_name") or "").strip().lower()
        if rn == "pytest":
            return "Run tests (pytest)"
        return "Run allowlisted command"
    rel = (payload.get("relative_path") or payload.get("relative_dir") or "").strip()
    sc, _ = host_action_scope_and_risk(
        ha,
        relative_path=rel or None,
        payload=payload if ha == "read_multiple_files" else None,
    )
    return reason_for_scope(sc)


def card_message_for_host_payload(payload: dict[str, Any]) -> str:
    """Short API `message` for permission_required JSON (no UI narration)."""
    ha = (payload.get("host_action") or "").strip().lower()
    if ha == "list_directory":
        return "Nexa needs permission to read this folder before continuing."
    if ha == "find_files":
        return "Nexa needs permission to search this folder before continuing."
    if ha in ("file_read", "read_multiple_files"):
        return "Nexa needs permission to read local files before continuing."
    if ha == "file_write":
        return "Nexa needs permission to write this file before continuing."
    return "Nexa needs permission before continuing."


def permission_fields_for_enqueue_payload(payload: dict[str, Any]) -> tuple[str, str, str]:
    """Return (scope, target_abs_str_for_row, risk_level) for AccessPermission.target."""
    wr = default_work_root_path()
    paths = resolve_host_executor_permission_paths(wr, payload)
    ha = (payload.get("host_action") or "").strip().lower()
    rel = (payload.get("relative_path") or payload.get("relative_dir") or "").strip()
    scope, risk = host_action_scope_and_risk(
        ha,
        relative_path=rel or None,
        payload=payload if ha == "read_multiple_files" else None,
    )
    tgt = str(paths[0].resolve()) if paths else str(wr.resolve())
    return scope, tgt[:8000], risk


def precheck_host_executor_permissions(
    db: Session,
    owner_user_id: str,
    payload: dict[str, Any],
) -> tuple[bool, str]:
    """Mirror worker permission check. When enforcement is off, always allowed."""
    from app.services.runtime_capabilities import audit_permission_bypassed, autonomy_test_mode

    if autonomy_test_mode():
        audit_permission_bypassed(
            db,
            user_id=owner_user_id,
            tool="host_executor_precheck",
            scope="host_executor",
            risk="dev_mode",
            extra={"host_action": (payload.get("host_action") or "")[:120]},
        )
        return True, ""
    if not getattr(get_settings(), "nexa_access_permissions_enforced", False):
        return True, ""
    ha = (payload.get("host_action") or "").strip().lower()
    wr = default_work_root_path()
    ok, err, _ = check_host_executor_job(
        db,
        owner_user_id=str(owner_user_id),
        host_action=ha or "unknown",
        work_root=wr,
        payload=payload,
    )
    return ok, err


def permission_required_payload(
    *,
    permission_request_id: int,
    scope: str,
    target: str,
    reason: str,
    risk_level: str,
    message: str | None = None,
) -> dict[str, Any]:
    """Structured payload for Web UI inline permission cards (Telegram ignores)."""
    return {
        "type": "permission_required",
        "permission_request_id": str(int(permission_request_id)),
        "scope": scope,
        "target": target,
        "reason": reason,
        "risk_level": risk_level,
        "grant_options": ["once", "session"],
        "message": message
        or (f"Nexa needs permission ({scope}) for this path before continuing."),
    }


def request_permission_from_chat(
    db: Session,
    owner_user_id: str,
    *,
    scope: str,
    target: str,
    risk_level: str,
    reason: str,
    metadata: dict[str, Any] | None = None,
    pending_payload: dict[str, Any] | None = None,
    pending_title: str | None = None,
    web_session_id: str | None = None,
    assignment_id: int | None = None,
    assigned_to_handle: str | None = None,
    organization_id: str | None = None,
) -> tuple[str, AccessPermission, bool]:
    """
    Create or reuse a pending AccessPermission row and return the chat message.

    Stores ``pending_payload`` on the permission row for approve-and-resume (must be stamped).

    Returns (message, row, reused_existing_pending).
    """
    tgt = (target or "").strip()
    dup = find_pending_permission_duplicate(db, owner_user_id, scope=scope, target=tgt)
    if dup:
        msg = format_awaiting_permission_duplicate(permission_id=dup.id)
        return msg, dup, True
    meta = {**(metadata or {}), "source": "chat_permission_flow"}
    if organization_id and str(organization_id).strip():
        meta["organization_id"] = str(organization_id).strip()[:64]
    if assignment_id is not None:
        meta["assignment_id"] = int(assignment_id)
        meta["agent_assignment_id"] = int(assignment_id)
    if assigned_to_handle:
        meta["assigned_to_handle"] = str(assigned_to_handle).strip()[:64]
    if pending_payload is not None:
        meta["pending_payload"] = pending_payload
    if pending_title:
        meta["pending_title"] = (pending_title or "")[:255]
    if web_session_id:
        meta["web_session_id"] = (web_session_id or "").strip()[:64]
    row = request_permission(
        db,
        owner_user_id,
        scope=scope,
        target=tgt[:8000],
        risk_level=risk_level,
        reason=(reason or "")[:4000] if reason else None,
        metadata=meta,
    )
    msg = format_permission_request_prompt(
        scope=scope,
        target=tgt[:8000],
        risk_level=risk_level,
        reason=reason,
    )
    return msg, row, False


def is_permission_row_denied(db: Session, permission_id: int | None) -> bool:
    if permission_id is None:
        return False
    row = db.get(AccessPermission, int(permission_id))
    return bool(row and row.status == STATUS_DENIED)
