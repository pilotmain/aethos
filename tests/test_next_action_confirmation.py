"""Next-step confirmation parser and apply logic."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base
from app.models.conversation_context import ConversationContext
from app.services import next_action_apply as naa
from app.services import next_action_confirmation as nac
from app.services.suggested_action_storage import build_suggested_actions_payload


def _one_action(cmd: str) -> list[nac.SuggestedAction]:
    now = datetime.now(timezone.utc).isoformat()
    return [
        nac.SuggestedAction(
            index=1, label=cmd, command=cmd, risk="low", created_at=now
        )
    ]


def _three() -> str:
    return build_suggested_actions_payload(
        [
            "@marketing create a LinkedIn post for this product",
            "@research compare competitors",
            "/doc create pdf Marketing Plan",
        ]
    )


def test_yes_picks_sole_suggestion() -> None:
    actions = _one_action("@marketing analyze https://a.com")
    t = nac.interpret_next_action_user_message("yes", actions, None)
    assert not t.no_match
    assert t.reprocess_user_text
    assert "a.com" in t.reprocess_user_text


def test_yes_is_ambiguous_when_multiple() -> None:
    raw = _three()
    actions = nac.parse_suggested_actions_from_context(raw)
    t = nac.interpret_next_action_user_message("yes", actions, None)
    assert t.immediate_assistant and "1" in t.immediate_assistant
    assert "Which" in t.immediate_assistant


def test_first_and_second() -> None:
    raw = _three()
    actions = nac.parse_suggested_actions_from_context(raw)
    t1 = nac.interpret_next_action_user_message("do the first one", actions, None)
    assert t1.reprocess_user_text and t1.reprocess_user_text.strip().startswith("@marketing")
    t2 = nac.interpret_next_action_user_message("second", actions, None)
    assert t2.reprocess_user_text and t2.reprocess_user_text.strip().startswith("@research")


def test_number_and_option2() -> None:
    raw = _three()
    actions = nac.parse_suggested_actions_from_context(raw)
    assert nac.interpret_next_action_user_message("2", actions, None).reprocess_user_text
    assert nac.interpret_next_action_user_message("option 3", actions, None).reprocess_user_text
    t = nac.interpret_next_action_user_message("5", actions, None)
    assert t.immediate_assistant and "1" in t.immediate_assistant


def test_expired_ignored() -> None:
    old = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    actions = [
        nac.SuggestedAction(1, "a", "@marketing a", "low", old)
    ]
    t = nac.interpret_next_action_user_message("yes", actions, None)
    assert t.immediate_assistant
    assert "don’t" in t.immediate_assistant.lower() or "don't" in t.immediate_assistant.lower()
    t2 = nac.interpret_next_action_user_message("unrelated", actions, None)
    assert t2.no_match or (not t2.reprocess_user_text and t2.immediate_assistant is None)  # noqa: SIM201


def test_injectable_doc_routes() -> None:
    actions = _one_action("/doc create pdf my doc")
    t = nac.interpret_next_action_user_message("1", actions, None)
    assert t.reprocess_user_text and t.reprocess_user_text.startswith("/doc")


def test_unknown_phrase_needs_run_flow() -> None:
    """Non-@, non-/ lines go through pending, not reprocess, until 'run'."""
    actions = _one_action("some freeform marketing idea for this week")
    t0 = nac.interpret_next_action_user_message("yes", actions, None)
    assert t0.store_pending_command
    assert t0.immediate_assistant and "run" in t0.immediate_assistant.lower()
    pend = {
        "command": t0.store_pending_command,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    t1 = nac.interpret_next_action_user_message(
        "run", [], json.dumps(pend, ensure_ascii=False)
    )
    assert t1.reprocess_user_text == t0.store_pending_command


def test_at_dev_inject_still_uses_inject() -> None:
    actions = _one_action("@dev add tests for the parser")
    t = nac.interpret_next_action_user_message("1", actions, None)
    assert t.reprocess_user_text and t.reprocess_user_text.startswith("@dev")
    # Risk class high — still inject; approval lives in dev path
    assert nac.risk_for_suggestion_command(t.reprocess_user_text) == "high"


@pytest.fixture
def in_memory_db() -> Session:
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    # minimal User + ConversationContext if needed; next_action uses cctx from table
    sm = sessionmaker(bind=e)()
    # conversation_contexts table exists from Base
    yield sm
    sm.close()


def test_do_the_marketing_one_phrase() -> None:
    raw = _three()
    actions = nac.parse_suggested_actions_from_context(raw)
    t = nac.interpret_next_action_user_message("do the marketing one", actions, None, None)
    assert not t.no_match
    assert t.reprocess_user_text
    assert "@marketing" in t.reprocess_user_text
    assert t.ack_line and "Running next step" in t.ack_line and "@" in t.ack_line


def test_do_the_research_one_phrase() -> None:
    raw = _three()
    actions = nac.parse_suggested_actions_from_context(raw)
    t = nac.interpret_next_action_user_message("the research one", actions, None, None)
    assert t.reprocess_user_text and "@research" in t.reprocess_user_text
    assert t.ack_line


def test_do_it_again_uses_last_injected() -> None:
    import json
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    raw = _three()
    actions = nac.parse_suggested_actions_from_context(raw)
    lastj = json.dumps(
        {
            "command": "@research compare competitors",
            "created_at": now.isoformat(),
        },
        ensure_ascii=False,
    )
    t = nac.interpret_next_action_user_message("do it again", actions, None, lastj, now=now)
    assert t.reprocess_user_text
    assert "competitor" in t.reprocess_user_text
    assert t.ack_line


def test_apply_on_in_memory_session(in_memory_db: Session) -> None:
    db = in_memory_db
    cctx = ConversationContext(
        user_id="u1",
        recent_messages_json="[]",
        last_suggested_actions_json=build_suggested_actions_payload(
            ['@dev echo "n"  # x']
        ),
    )
    db.add(cctx)
    db.commit()
    cctx2 = db.get(ConversationContext, cctx.id) or cctx
    r = naa.apply_next_action_to_user_text(db, cctx2, "first")
    assert r.user_text_for_pipeline
    assert r.is_injection
    assert r.inject_ack and "Running next step" in r.inject_ack
    cctx3 = db.get(ConversationContext, cctx2.id) or cctx2
    assert cctx3.last_suggested_actions_json in (None, "null", "")
    assert cctx3.last_injected_action_json
