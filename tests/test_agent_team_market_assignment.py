"""Market/topic assignments must not trigger local folder clarification or host synthetic paths."""

from __future__ import annotations

import uuid

import pytest

from app.core.db import SessionLocal, ensure_schema
from app.models.user import User
from app.models.user_agent import UserAgent
from app.services.agent_team.chat import try_agent_team_chat_turn
from app.services.agent_team.host_bridge import infer_host_payload_for_assignment_text
from app.services.agent_team.planner import (
    assignment_skips_host_path_inference,
    build_assignment_input_json,
    classify_assignment_instruction_kind,
    plan_tasks_from_goal,
    topic_market_assignment_intent,
)


@pytest.fixture
def db_session():
    ensure_schema()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def test_topic_market_intent_detects_summarize_market_prompt() -> None:
    t = "summarize this market: AI customer support tools for small businesses"
    assert topic_market_assignment_intent(t) is True
    assert assignment_skips_host_path_inference(t) is True


def test_explicit_folder_still_filesystem_kind() -> None:
    t = "analyze folder /Users/example/lifeos"
    assert classify_assignment_instruction_kind(t) == "file_folder"
    assert assignment_skips_host_path_inference(t) is False


def test_infer_host_payload_none_for_market_text(db_session) -> None:
    uid = f"m_{uuid.uuid4().hex[:10]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    pl = infer_host_payload_for_assignment_text(
        db_session,
        user_id=uid,
        text="summarize this market: AI widgets",
        web_session_id="default",
    )
    assert pl is None


def test_plan_tasks_market_goal_sets_kind(db_session) -> None:
    plans = plan_tasks_from_goal(
        "summarize this market: AI customer support tools for small businesses"
    )
    assert plans and plans[0].get("assigned_to") == "research-analyst"
    ij = plans[0].get("input_json") or {}
    assert ij.get("kind") == "market_analysis"
    assert "customer support" in (ij.get("topic") or "").lower()


def test_assign_chat_creates_market_assignment_no_folder_question(
    monkeypatch: pytest.MonkeyPatch, db_session
) -> None:
    uid = f"m_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()

    monkeypatch.setattr(
        "app.services.agent_team.service.run_custom_user_agent",
        lambda *_a, **_k: "**Stub market summary.**",
    )
    monkeypatch.setattr(
        "app.services.agent_team.service.try_assignment_host_dispatch",
        lambda *_a, **_k: None,
    )

    db_session.add(
        UserAgent(
            owner_user_id=uid,
            agent_key="research_analyst",
            display_name="RA",
            description="",
            system_prompt="You research.",
        )
    )
    db_session.commit()

    msg = (
        "assign @research-analyst to summarize this market: "
        "AI customer support tools for small businesses"
    )
    out = try_agent_team_chat_turn(db_session, uid, msg, web_session_id="default")
    assert out is not None
    body = out.reply.lower()
    assert "which folder should i read" not in body
    assert "assignment not created" not in body
    assert "stub market summary" in body or "research" in body or "#" in out.reply


def test_build_input_json_market() -> None:
    ij = build_assignment_input_json(
        "summarize this market: widgets for SMB", kind="market_analysis"
    )
    assert ij["kind"] == "market_analysis"
    assert "widgets" in ij.get("topic", "").lower()
