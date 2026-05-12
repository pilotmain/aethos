"""Suggested-action persistence on ConversationContext."""

from __future__ import annotations

from app.services.conversation_context_service import get_or_create_context
from app.services.suggested_action_storage import save_suggested_actions_if_shown


def test_save_suggested_actions_defines_context(db_session) -> None:
    uid = "tg_suggested_storage_smoke_1"
    save_suggested_actions_if_shown(
        db_session,
        uid,
        ["Run tests", "Deploy to staging"],
        user_message="ok",
    )
    cctx = get_or_create_context(db_session, uid)
    assert cctx.last_suggested_actions_json
    assert "Run tests" in cctx.last_suggested_actions_json
