"""Host-executor bridge for agent assignments: infer payload, validate paths, permission, enqueue."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.agent_team import AgentAssignment
from app.services.agent_team.planner import assignment_skips_host_path_inference
from app.services.audit_service import audit
from app.services.content_provenance import InstructionSource, apply_trusted_instruction_source
from app.services.conversation_context_service import get_or_create_context
from app.services.host_executor_chat import (
    _validate_enqueue_payload,
    enqueue_host_job_from_validated_payload,
)
from app.services.host_executor_intent import infer_host_executor_action, title_for_payload
from app.services.local_file_intent import infer_local_file_request
from app.services.nexa_safety_policy import stamp_host_payload
from app.services.nexa_workspace_project_registry import (
    active_project_relative_base,
    merge_payload_with_project_base,
)
from app.services.permission_request_flow import (
    card_message_for_host_payload,
    derive_permission_reason,
    is_permission_eligible_precheck_failure,
    permission_fields_for_enqueue_payload,
    permission_required_payload,
    precheck_host_executor_permissions,
    reason_for_host_payload,
    request_permission_from_chat,
    validate_host_payload_paths_before_permission,
)

logger = logging.getLogger(__name__)


def precheck_assignment_host_user_message(
    db: Session,
    *,
    user_id: str,
    user_message: str,
    web_session_id: str | None,
) -> tuple[bool, str | None]:
    """
    Validate host-shaped assignment text **before** creating an AgentAssignment row.

    Returns (False, user_safe_error) when inference fails or paths do not exist.
    Returns (True, None) for LLM-only tasks (no deterministic host payload).
    """
    if assignment_skips_host_path_inference(user_message):
        return True, None
    inferred = infer_host_payload_for_assignment_text(
        db, user_id=user_id, text=user_message, web_session_id=web_session_id
    )
    if inferred is None:
        return True, None
    if "__assignment_error__" in inferred:
        return False, str(inferred["__assignment_error__"] or "Invalid request.")[:4000]
    pv_ok, pv_err = validate_host_payload_paths_before_permission(inferred)
    if not pv_ok:
        return False, (pv_err or "Path validation failed.")[:4000]
    return True, None


def infer_host_payload_for_assignment_text(
    db: Session,
    *,
    user_id: str,
    text: str,
    web_session_id: str | None,
) -> dict[str, Any] | None:
    """Mirror deterministic host infer without ConversationContext mutations."""
    t0 = (text or "").strip()
    if not t0:
        return None
    # Market/topic assignments must never synthesize folder reads or ``/app/market`` paths.
    if assignment_skips_host_path_inference(t0):
        return None

    wid = (web_session_id or "default").strip()[:64] or "default"
    cctx = get_or_create_context(db, user_id, web_session_id=wid)
    base = active_project_relative_base(db, user_id, cctx)

    inferred = infer_host_executor_action(t0)
    if not inferred:
        lf = infer_local_file_request(t0, default_relative_base=base)
        if lf.matched and lf.error_message:
            return {"__assignment_error__": lf.error_message}
        if lf.matched and lf.clarification_message:
            return {"__assignment_error__": lf.clarification_message}
        if lf.matched and lf.path_resolution_failed:
            return {"__assignment_error__": "That path is not allowed or not under the configured work root."}
        if lf.matched and lf.payload:
            inferred = lf.payload
    if not inferred:
        return None

    if base != ".":
        inferred = merge_payload_with_project_base(dict(inferred), base)

    inferred = apply_trusted_instruction_source(
        dict(inferred), InstructionSource.USER_MESSAGE.value
    )
    return inferred


def try_assignment_host_dispatch(
    db: Session,
    *,
    row: AgentAssignment,
    uid: str,
) -> dict[str, Any] | None:
    """
    If assignment maps to a host action, enqueue, request permission, or fail.

    Returns a **terminal** dict for dispatch_assignment, or None to continue with LLM.
    """
    ij = row.input_json or {}
    if (ij.get("kind") or "") in ("market_analysis", "topic_analysis"):
        return None
    body = ij.get("user_message") or row.description or ""
    inferred = infer_host_payload_for_assignment_text(
        db, user_id=uid, text=body, web_session_id=row.web_session_id
    )
    if inferred is None:
        return None
    if "__assignment_error__" in inferred:
        msg = str(inferred["__assignment_error__"] or "")[:4000]
        return {"ok": False, "error": msg, "assignment_id": row.id, "failed_validation": True}

    pv_ok, pv_err = validate_host_payload_paths_before_permission(inferred)
    if not pv_ok:
        return {
            "ok": False,
            "error": pv_err or "Path validation failed.",
            "assignment_id": row.id,
            "failed_validation": True,
        }

    ok_pre, err_pre = precheck_host_executor_permissions(db, uid, inferred)
    if not ok_pre:
        if is_permission_eligible_precheck_failure(err_pre, inferred):
            scope_t, target_t, risk_t = permission_fields_for_enqueue_payload(inferred)
            reason_t = derive_permission_reason(
                scope_t, reason_override=reason_for_host_payload(inferred)
            )
            stamped_infer = stamp_host_payload(
                apply_trusted_instruction_source(
                    dict(inferred),
                    InstructionSource.USER_MESSAGE.value,
                )
            )
            stamped_infer["agent_assignment_id"] = row.id
            ws_id = (row.web_session_id or "default").strip()[:64] or "default"
            title = title_for_payload(inferred)
            msg_pr, row_pr, _reused = request_permission_from_chat(
                db,
                uid,
                scope=scope_t,
                target=target_t,
                risk_level=risk_t,
                reason=reason_t,
                metadata={
                    "host_action": (inferred.get("host_action") or "")[:64],
                },
                pending_payload=stamped_infer,
                pending_title=title,
                web_session_id=ws_id,
                assignment_id=row.id,
                assigned_to_handle=row.assigned_to_handle,
            )
            row.status = "waiting_approval"
            row.error = None
            inp = dict(row.input_json or {})
            inp["pending_permission_id"] = row_pr.id
            row.input_json = inp
            db.add(row)
            db.commit()
            db.refresh(row)
            audit(
                db,
                event_type="agent_assignment.waiting_approval",
                actor="aethos",
                user_id=uid,
                message=f"Assignment #{row.id} waiting for permission #{row_pr.id}",
                metadata={
                    "assignment_id": row.id,
                    "permission_request_id": row_pr.id,
                    "assigned_to_handle": row.assigned_to_handle,
                },
            )
            pr_line = card_message_for_host_payload(inferred)
            perm_req = permission_required_payload(
                permission_request_id=row_pr.id,
                scope=scope_t,
                target=target_t,
                reason=reason_t,
                risk_level=risk_t,
                message=pr_line,
            )
            return {
                "ok": True,
                "waiting_approval": True,
                "permission_id": row_pr.id,
                "assignment_id": row.id,
                "message": msg_pr,
                "permission_required": perm_req,
            }
        return {
            "ok": False,
            "error": (err_pre or "That path isn’t allowed for host actions.")[:3500],
            "assignment_id": row.id,
        }

    trusted = apply_trusted_instruction_source(dict(inferred), InstructionSource.USER_MESSAGE.value)
    safe_pl = _validate_enqueue_payload(trusted)
    if not safe_pl:
        return {
            "ok": False,
            "error": "That host action could not be validated for execution.",
            "assignment_id": row.id,
        }

    if not getattr(get_settings(), "nexa_host_executor_enabled", False):
        return {
            "ok": False,
            "error": "Host execution is disabled on this server (`NEXA_HOST_EXECUTOR_ENABLED`).",
            "assignment_id": row.id,
        }

    title = title_for_payload(safe_pl)
    ws_id = (row.web_session_id or "default").strip()[:64] or "default"
    job = enqueue_host_job_from_validated_payload(
        db,
        uid,
        safe_pl=safe_pl,
        title=title,
        web_session_id=ws_id,
        access_permission_resume=False,
        agent_assignment_id=row.id,
    )

    row.status = "running"
    row.started_at = row.started_at or __import__("datetime").datetime.utcnow()
    row.output_json = {
        "host_job_id": job.id,
        "kind": "host_executor_queued",
        "note": "Host job queued from assignment.",
    }
    row.error = None
    db.add(row)
    db.commit()
    db.refresh(row)
    audit(
        db,
        event_type="agent_assignment.dispatched",
        actor="aethos",
        user_id=uid,
        message=f"Assignment #{row.id} host job #{job.id}",
        metadata={
            "assignment_id": row.id,
            "host_job_id": job.id,
        },
    )
    return {
        "ok": True,
        "assignment_id": row.id,
        "host_job_id": job.id,
        "output": row.output_json,
    }
