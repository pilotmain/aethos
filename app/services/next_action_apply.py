"""DB wiring for co-pilot next-step confirmation (Telegram + Web)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.conversation_context import ConversationContext
from app.services.host_executor_chat import (
    evaluate_deterministic_host_permission_turn,
    may_run_pre_llm_deterministic_host,
    try_apply_host_executor_turn,
)
from app.services.lightweight_workflow import (
    append_adhoc_committed_action,
    flow_step_exists_for_command,
    interpret_flow_user_message,
    mark_flow_step_done,
)
from app.services.nexa_workspace_project_registry import try_workspace_project_nl_turn
from app.services.next_action_confirmation import (
    interpret_next_action_user_message,
    parse_suggested_actions_from_context,
)

logger = logging.getLogger(__name__)

_MAX_INJECT_DEPTH = 1


@dataclass(frozen=True)
class NextActionApplicationResult:
    early_assistant: str | None  # if set, short-circuit: show this, no LLM
    user_text_for_pipeline: str
    is_injection: bool
    had_match: bool  # True if this module handled a confirmation-like turn (even for early reply)
    # When is_injection: prepend to the main assistant message this turn (Web + Telegram)
    inject_ack: str | None = None
    related_job_ids: tuple[int, ...] = ()
    # Muted web system-event rows (kind, text); host executor queue / UX only
    pending_system_events: tuple[tuple[str, str], ...] = ()
    # Inline permission card for Web (`type: permission_required`); Telegram ignores.
    permission_required: dict[str, Any] | None = None


def clear_next_action_state(cctx: ConversationContext) -> None:
    cctx.last_suggested_actions_json = None
    cctx.next_action_pending_inject_json = None


def set_pending_inject_for_command(cctx: ConversationContext, command: str) -> None:
    c = (command or "").strip()
    if not c:
        return
    cctx.next_action_pending_inject_json = json.dumps(
        {
            "command": c,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
    )


def set_last_injected_from_command(cctx: ConversationContext, command: str) -> None:
    c = (command or "").strip()
    if not c:
        return
    cctx.last_injected_action_json = json.dumps(
        {
            "command": c,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
    )


def apply_next_action_to_user_text(
    db: Session,
    cctx: ConversationContext,
    user_text: str,
    *,
    depth: int = 0,
    web_session_id: str | None = None,
) -> NextActionApplicationResult:
    """
    Returns updated user line for the normal pipeline, or a short-circuit assistant reply.
    """
    t0 = (user_text or "").strip()
    if not t0:
        return NextActionApplicationResult(None, t0, False, False, None)
    if depth > _MAX_INJECT_DEPTH:
        return NextActionApplicationResult(None, t0, False, False, None)

    hx = try_apply_host_executor_turn(
        db, cctx, t0, web_session_id=web_session_id
    )
    if hx is not None:
        return hx

    if get_settings().nexa_host_executor_enabled and may_run_pre_llm_deterministic_host(cctx):
        det = evaluate_deterministic_host_permission_turn(
            db, cctx, t0, web_session_id=web_session_id
        )
        if det is not None:
            logger.info(
                "permission_flow source=deterministic_pre_llm permission_required=%s",
                bool(det.permission_required),
            )
            return det

    proj_reply = try_workspace_project_nl_turn(db, cctx, t0, owner_user_id=cctx.user_id)
    if proj_reply:
        return NextActionApplicationResult(proj_reply, t0, False, True, None)

    actions = parse_suggested_actions_from_context(cctx.last_suggested_actions_json)
    r = interpret_next_action_user_message(
        t0,
        actions,
        cctx.next_action_pending_inject_json,
        cctx.last_injected_action_json,
    )

    if r.no_match:
        fr = interpret_flow_user_message(t0, cctx)
        if fr.no_match:
            return NextActionApplicationResult(None, t0, False, False, None)
        if fr.reprocess_user_text:
            clear_next_action_state(cctx)
            cmd0 = (fr.reprocess_user_text or "").strip()
            set_last_injected_from_command(cctx, cmd0)
            if flow_step_exists_for_command(cctx, cmd0):
                mark_flow_step_done(cctx, cmd0)
            else:
                append_adhoc_committed_action(cctx, cmd0)
            _commit(db, cctx)
            return NextActionApplicationResult(
                None, cmd0, True, True, fr.ack_line
            )
        if fr.immediate_assistant and fr.store_pending_freeform:
            set_pending_inject_for_command(cctx, (fr.store_pending_freeform or "").strip())
            _commit(db, cctx)
            return NextActionApplicationResult(
                fr.immediate_assistant, t0, False, True, None
            )
        if fr.immediate_assistant:
            if fr.clear_suggestions:
                clear_next_action_state(cctx)
            _commit(db, cctx)
            return NextActionApplicationResult(fr.immediate_assistant, t0, False, True, None)
        if fr.clear_suggestions:
            clear_next_action_state(cctx)
            _commit(db, cctx)
        return NextActionApplicationResult(None, t0, False, True, None)

    if r.reprocess_user_text:
        clear_next_action_state(cctx)
        cmd0 = (r.reprocess_user_text or "").strip()
        set_last_injected_from_command(cctx, cmd0)
        if flow_step_exists_for_command(cctx, cmd0):
            mark_flow_step_done(cctx, cmd0)
        else:
            append_adhoc_committed_action(cctx, cmd0)
        _commit(db, cctx)
        return NextActionApplicationResult(None, cmd0, True, True, r.ack_line)

    if r.immediate_assistant and r.store_pending_command:
        set_pending_inject_for_command(cctx, r.store_pending_command)
        _commit(db, cctx)
        return NextActionApplicationResult(r.immediate_assistant, t0, False, True, None)

    if r.immediate_assistant and r.clear_suggestions:
        clear_next_action_state(cctx)
        _commit(db, cctx)
        return NextActionApplicationResult(r.immediate_assistant, t0, False, True, None)

    if r.immediate_assistant:
        _commit(db, cctx)
        return NextActionApplicationResult(r.immediate_assistant, t0, False, True, None)

    if r.clear_suggestions:
        clear_next_action_state(cctx)
        _commit(db, cctx)
    return NextActionApplicationResult(None, t0, False, False, None)


def _commit(db: Session, cctx: ConversationContext) -> None:
    try:
        db.add(cctx)
        db.commit()
    except Exception:  # noqa: BLE001
        logger.debug("next_action _commit", exc_info=True)
        db.rollback()
