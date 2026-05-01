"""Lightweight co-pilot flow: goal, steps, next, integration with next_action."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base
from app.models.conversation_context import ConversationContext
from app.services import next_action_apply as naa
from app.services import next_action_confirmation as nac
from app.services.lightweight_workflow import (
    append_adhoc_committed_action,
    flow_step_exists_for_command,
    format_flow_bullet_summary,
    interpret_flow_user_message,
    merge_or_create_flow_state_from_suggestions,
    mark_flow_step_done,
)
from app.services.suggested_action_storage import build_suggested_actions_payload


def _cctx() -> ConversationContext:
    return ConversationContext(
        user_id="u_flow",
        recent_messages_json="[]",
    )


def _three_lines() -> list[str]:
    return [
        "@marketing create a LinkedIn post for this product",
        "@research compare competitors",
        "/doc create pdf Marketing Plan",
    ]


def test_goal_and_steps_from_next_block() -> None:
    c = _cctx()
    merge_or_create_flow_state_from_suggestions(
        c, "help me market pilotmain.com", _three_lines()
    )
    st = json.loads(c.current_flow_state_json or "{}")
    assert "pilot" in (st.get("goal") or "").lower() or "pilot" in (st.get("goal") or "")
    assert st.get("steps")
    assert len(st["steps"]) == 3
    assert st["steps"][0]["type"] == "marketing"
    assert st["steps"][0]["status"] == "pending"


def test_marks_step_done_on_execution() -> None:
    c = _cctx()
    merge_or_create_flow_state_from_suggestions(
        c, "market pilotmain.com", _three_lines()
    )
    mark_flow_step_done(
        c,
        "@marketing create a LinkedIn post for this product",
    )
    st = json.loads(c.current_flow_state_json or "{}")
    assert st["steps"][0]["status"] == "done"
    assert st["steps"][1]["status"] == "pending"


def test_next_runs_first_pending() -> None:
    c = _cctx()
    merge_or_create_flow_state_from_suggestions(
        c, "goal g", ["/doc a short doc about the product"]
    )
    r = interpret_flow_user_message("next", c, now=datetime.now(timezone.utc))
    assert not r.no_match
    assert r.reprocess_user_text and r.reprocess_user_text.strip().startswith("/doc")
    assert r.ack_line and "Running next step" in r.ack_line


def test_ambiguous_next_asks() -> None:
    c = _cctx()
    merge_or_create_flow_state_from_suggestions(
        c, "goal g", _three_lines()[:3]  # all pending
    )
    r = interpret_flow_user_message("next", c, now=datetime.now(timezone.utc))
    assert not r.no_match
    assert r.immediate_assistant
    assert "which" in r.immediate_assistant.lower() or "1" in r.immediate_assistant
    assert not r.reprocess_user_text


def test_what_is_next_info_no_auto_inject() -> None:
    c = _cctx()
    merge_or_create_flow_state_from_suggestions(
        c, "goal g", _three_lines()[:2]
    )
    st = json.loads(c.current_flow_state_json or "{}")
    r = interpret_flow_user_message("where are we", c, now=datetime.now(timezone.utc))
    assert not r.no_match
    assert r.immediate_assistant
    assert format_flow_bullet_summary(st) in r.immediate_assistant
    assert not r.reprocess_user_text


def test_no_auto_chain_multiple() -> None:
    """'next' with 3 never injects 3 in one go — user gets clarification or first pending in single-pend."""
    c = _cctx()
    merge_or_create_flow_state_from_suggestions(c, "g", _three_lines()[:3])
    r1 = interpret_flow_user_message("next", c, now=datetime.now(timezone.utc))
    # three pendings: ambiguous, no reprocess
    assert not r1.reprocess_user_text


def test_integrates_with_apply_next_action_first() -> None:
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    c0 = _cctx()
    s.add(c0)
    s.commit()
    c = s.get(ConversationContext, c0.id) or c0
    merge_or_create_flow_state_from_suggestions(
        c, "g", ["/doc x", "@research y"]
    )
    c.last_suggested_actions_json = build_suggested_actions_payload(
        ["/doc x", "@research y"]
    )
    s.add(c)
    s.commit()
    c2 = s.get(ConversationContext, c0.id) or c0
    a = naa.apply_next_action_to_user_text(s, c2, "1")
    assert a.is_injection
    c3 = s.get(ConversationContext, c0.id) or c0
    st = json.loads(c3.current_flow_state_json or "{}")
    assert st["steps"][0]["status"] == "done"


def test_works_with_injectable_dev_approval_unchanged() -> None:
    c = _cctx()
    merge_or_create_flow_state_from_suggestions(
        c, "g", ["@dev add a unit test for next_action"]
    )
    r = interpret_flow_user_message("next", c, now=datetime.now(timezone.utc))
    assert r.reprocess_user_text and r.reprocess_user_text.strip().startswith("@dev")
    # no extra automation — pipeline + dev still enforce jobs (not asserted here)
    assert r.ack_line


def test_freeform_next_step_uses_run_gate() -> None:
    c = _cctx()
    merge_or_create_flow_state_from_suggestions(
        c, "g", ["refine the landing copy for clarity"]
    )
    r = interpret_flow_user_message("go ahead", c, now=datetime.now(timezone.utc))
    assert r.store_pending_freeform
    assert "run" in (r.immediate_assistant or "").lower()


def test_adhoc_inject_appends() -> None:
    c = _cctx()
    append_adhoc_committed_action(c, "/doc export summary")
    st = json.loads(c.current_flow_state_json or "{}")
    assert len(st.get("steps") or []) == 1
    assert st["steps"][0]["status"] == "done"
    assert flow_step_exists_for_command(c, "/doc export summary")


def test_flow_expiry_message() -> None:
    c = _cctx()
    c.current_flow_state_json = json.dumps(
        {
            "goal": "old",
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "updated_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            "steps": [{"index": 1, "type": "marketing", "status": "pending", "command": "@a b"}],
            "last_action": None,
        }
    )
    r = interpret_flow_user_message("next", c, now=datetime.now(timezone.utc))
    assert not r.no_match
    assert "moved on" in (r.immediate_assistant or "").lower()
    assert c.current_flow_state_json is None


def test_persisted_suggested_patches_flow_done_state() -> None:
    c = _cctx()
    lines = ["/doc one", "/doc two"]
    merge_or_create_flow_state_from_suggestions(c, "g", lines)
    mark_flow_step_done(c, "/doc one")
    # New suggestions: same /doc one line — step stays done
    merge_or_create_flow_state_from_suggestions(
        c, "g2", ["/doc one", "@marketing three"]
    )
    st = json.loads(c.current_flow_state_json or "{}")
    d1 = [x for x in st["steps"] if "/doc one" in (x.get("command") or "")][0]
    assert d1["status"] == "done"
