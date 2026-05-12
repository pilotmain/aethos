"""Persist the last 'Next steps' list on ConversationContext (co-pilot)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.services.conversation_context_service import get_or_create_context
from app.services.lightweight_workflow import merge_or_create_flow_state_from_suggestions
from app.services.next_action_confirmation import command_from_suggestion_line, risk_for_suggestion_command
from app.services.web_request_context import get_web_session_id

logger = logging.getLogger(__name__)


def build_suggested_actions_payload(lines: list[str]) -> str:
    """JSON array of {index, label, command, risk, created_at}."""
    out: list[dict[str, str | int]] = []
    now = datetime.now(timezone.utc).isoformat()
    for i, line in enumerate(lines, start=1):
        if i > 4:
            break
        raw = (line or "").strip()
        if not raw:
            continue
        cmd = command_from_suggestion_line(raw)
        out.append(
            {
                "index": i,
                "label": raw[:1_200],
                "command": cmd[:1_200],
                "risk": risk_for_suggestion_command(cmd),
                "created_at": now,
            }
        )
    return json.dumps(out, ensure_ascii=False)


def save_suggested_actions_if_shown(
    db: Session | None,
    app_user_id: str | None,
    shown_lines: list[str] | None,
    *,
    user_message: str | None = None,
) -> None:
    """Replaces any prior list when a new 'Next steps' block was shown to the user."""
    if not db or not (app_user_id or "").strip():
        return
    cctx = get_or_create_context(db, app_user_id, web_session_id=get_web_session_id())
    if not shown_lines:
        return
    clean = [str(x).strip() for x in shown_lines if str(x).strip()][:4]
    if not clean:
        cctx.last_suggested_actions_json = None
    else:
        cctx.last_suggested_actions_json = build_suggested_actions_payload(clean)
        merge_or_create_flow_state_from_suggestions(
            cctx, (user_message or "").strip() or None, clean
        )
    try:
        db.add(cctx)
        db.commit()
    except Exception:  # noqa: BLE001
        logger.debug("save_suggested_actions_if_shown: commit failed", exc_info=True)
        db.rollback()
