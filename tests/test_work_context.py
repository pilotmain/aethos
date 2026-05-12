# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Current work payload + /web/work-context (compact, for right panel)."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from unittest.mock import patch

from app.core.db import Base
from app.main import app
from app.models.conversation_context import ConversationContext
from app.services.work_context import build_work_context
from app.services import lightweight_workflow as lw
from app.services.lightweight_workflow import merge_or_create_flow_state_from_suggestions


@pytest.fixture
def in_memory_db() -> Session:
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    yield s
    s.close()


def test_current_work_summary_from_flow_state(in_memory_db: Session) -> None:
    c = ConversationContext(user_id="u_wc", recent_messages_json="[]")
    merge_or_create_flow_state_from_suggestions(
        c,
        "help me with Marketing pilotmain.com",
        [
            "/doc one",
            "@research two",
        ],
    )
    in_memory_db.add(c)
    in_memory_db.commit()
    c2 = in_memory_db.get(ConversationContext, c.id) or c
    d = build_work_context(in_memory_db, c2, "u_wc")
    f = d["flow"]
    assert f["has_flow"] is True
    assert f["total_steps"] == 2
    assert f["completed_steps"] == 0
    assert f["next_command"] and "doc" in f["next_command"]
    assert any("Current work:" in x for x in d["lines"])


@patch("app.core.security.get_settings")
def test_web_work_context_ok(mock_gs) -> None:
    m = type("S", (), {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    c = TestClient(app)
    r = c.get(
        "/api/v1/web/work-context?session_id=default",
        headers={"X-User-Id": "web_ctx_1"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert "flow" in j and "lines" in j and "recent_artifacts" in j
    assert "has_flow" in j["flow"]


def test_interpret_flow_resume_does_not_auto_inject() -> None:
    c = ConversationContext(user_id="u1", recent_messages_json="[]")
    lw.merge_or_create_flow_state_from_suggestions(
        c,
        "g",
        ["/doc a", "/doc b"],
    )
    t = lw.interpret_flow_user_message("resume", c, now=datetime.now(timezone.utc))
    assert not t.no_match
    assert t.immediate_assistant
    assert "next" in (t.immediate_assistant or "").lower() or "Next:" in (t.immediate_assistant or "")
    assert not t.reprocess_user_text


def test_where_are_we_workflow_complete() -> None:
    c = ConversationContext(user_id="u1", recent_messages_json="[]")
    lw.merge_or_create_flow_state_from_suggestions(
        c,
        "g",
        ["/doc a"],
    )
    c.current_flow_state_json = json.dumps(
        {
            "goal": "Test",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "steps": [
                {"index": 1, "type": "doc", "status": "done", "command": "/doc a"},
            ],
            "last_action": "/doc a",
        }
    )
    t = lw.interpret_flow_user_message("where are we", c, now=datetime.now(timezone.utc))
    assert not t.no_match
    assert t.immediate_assistant
    assert "Workflow complete" in (t.immediate_assistant or "")


def test_what_is_left_phrase_matches_info() -> None:
    from app.services.lightweight_workflow import _is_flow_info_query

    assert _is_flow_info_query("what's left?")
    assert _is_flow_info_query("whats left")


@patch("app.services.web_chat_service.process_web_message")
@patch("app.core.security.get_settings")
def test_web_chat_includes_system_events_ok(mock_gs, mock_chat) -> None:
    from app.services.web_chat_service import WebChatResult

    m = type("S", (), {"nexa_web_api_token": "secret", "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    mock_chat.return_value = WebChatResult(
        reply="x",
        intent="q",
        agent_key="research",
        system_events=[{"kind": "job", "text": "Job #1 queued."}],
    )
    c = TestClient(app)
    r = c.post(
        "/api/v1/web/chat",
        json={"message": "x"},
        headers={"X-User-Id": "web_x", "Authorization": "Bearer secret"},
    )
    j = r.json()
    assert j.get("system_events")
    assert j["system_events"][0]["text"]
