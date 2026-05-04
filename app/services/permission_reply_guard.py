"""
Defense-in-depth for web chat: strip legacy onboarding phrases from LLM output.

Primary control is deterministic host + permission handling in
``apply_next_action_to_user_text`` (runs before suggested-actions / LLM pipelines).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def permission_required_payload_from_blocked_host_json(cctx: Any) -> dict[str, Any] | None:
    """
    When `blocked_host_executor_json` is set (awaiting approval), rebuild the Web card payload
    so clients always get buttons even if only the LLM/guard path ran this turn.
    """
    raw = getattr(cctx, "blocked_host_executor_json", None)
    if not (raw or "").strip():
        return None
    try:
        blocked = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(blocked, dict):
        return None
    payload = blocked.get("payload")
    pid = blocked.get("permission_id")
    if not isinstance(payload, dict) or pid is None:
        return None
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return None
    from app.services.permission_request_flow import (
        card_message_for_host_payload,
        derive_permission_reason,
        permission_fields_for_enqueue_payload,
        permission_required_payload,
        reason_for_host_payload,
    )

    scope_t, target_t, risk_t = permission_fields_for_enqueue_payload(payload)
    reason_t = derive_permission_reason(
        scope_t, reason_override=reason_for_host_payload(payload)
    )
    return permission_required_payload(
        permission_request_id=pid_int,
        scope=scope_t,
        target=target_t,
        reason=reason_t,
        risk_level=risk_t,
        message=card_message_for_host_payload(payload),
    )


def reply_promises_local_fetch_without_execution(reply: str) -> bool:
    """LLM hedging copy when local listing/read was not actually queued."""
    if not (reply or "").strip():
        return False
    raw = reply.lower()
    return bool(
        re.search(
            r"(?i)(\bgot it\b.*\bfetch\b|\blet me fetch\b|\bi'?ll fetch\b|\bfetch that listing\b|\bget that listing\b)",
            raw,
        )
    )


def reply_contains_stale_permission_guidance(reply: str) -> bool:
    """Legacy onboarding phrases that conflict with inline permission cards."""
    if not (reply or "").strip():
        return False
    raw = reply.lower()
    norm = raw.replace("→", "->").replace("−", "-")
    if "already told you" in raw:
        return True
    if "system -> permissions" in norm or "system->permissions" in norm.replace(" ", ""):
        return True
    if "go to system" in raw and "permission" in raw:
        return True
    if "/permissions" in raw and ("go " in raw or "open " in raw or "visit " in raw or "see " in raw):
        return True
    if re.search(r"\bshould\s+i\s+(go\s+)?request\s+permission\b", raw):
        return True
    if "allow once" in raw or "allow for session" in raw:
        return True
    return False


def user_message_suggests_privileged_host_action(text: str) -> bool:
    """Fast heuristic — must stay in sync with broad local-file / host intent patterns."""
    t = (text or "").strip().lower()
    if not t:
        return False
    if re.search(
        r"(?i)(/users/|/home/|~/|\blist\s+files?\b|\bls\b|\bread\s+file\b|\bcat\b|\bwrite\b|"
        r"\bopen\b|\brun\s+tests?\b|\bpytest\b|\bgit\s+status\b|\bgit\s+push\b|\bvercel\b|\brun\s+pytest\b)",
        t,
    ):
        return True
    return False


def patch_llm_reply_for_permission_execution_layer(
    db: Session | None,
    cctx: Any,  # ConversationContext
    *,
    web_session_id: str,
    user_text: str,
    reply: str,
) -> tuple[str, dict[str, Any] | None, str | None, str | None]:
    """
    Post-LLM fallback only: replace known-bad onboarding copy. Does not infer host actions.

    Returns:
        (reply, permission_required|None, response_kind_override|None, intent_override|None)
    """
    needs_patch = reply_contains_stale_permission_guidance(reply) or (
        user_message_suggests_privileged_host_action(user_text)
        and reply_promises_local_fetch_without_execution(reply)
    )
    if not needs_patch:
        return reply, None, None, None

    pr_blocked = permission_required_payload_from_blocked_host_json(cctx)
    if pr_blocked:
        logger.info("permission_flow source=guard_blocked_context layer=post_llm")
        return ("🔐 **Permission required**", pr_blocked, "permission_required", None)

    if db is not None:
        from app.services.host_executor_chat import (
            evaluate_deterministic_host_permission_turn,
            may_run_pre_llm_deterministic_host,
        )

        if may_run_pre_llm_deterministic_host(cctx):
            det = evaluate_deterministic_host_permission_turn(
                db, cctx, user_text, web_session_id=web_session_id
            )
            if det is not None and det.permission_required:
                logger.info("permission_flow source=guard_second_chance_deterministic layer=post_llm")
                bubble = (det.early_assistant or "").strip() or "🔐 **Permission required**"
                return (bubble, det.permission_required, "permission_required", None)

    logger.info("permission_flow source=guard_stale_copy layer=post_llm")
    return ("🔐 **Permission required**", None, None, None)
