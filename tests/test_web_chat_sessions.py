# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Multi-session web chat: list, create, messages, work-context, chat scoping."""
from __future__ import annotations

import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.main import app
from app.models.conversation_context import ConversationContext
from app.schemas.web_ui import WebResponseSourceItem
from app.services.web_chat_service import WebChatResult


@patch("app.core.security.get_settings")
def test_web_create_session_list_and_messages(mock_gs) -> None:
    m = type("S", (), {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    uid = "web_multi_sess_1"
    c = TestClient(app)

    r0 = c.get("/api/v1/web/sessions", headers={"X-User-Id": uid})
    assert r0.status_code == 200
    assert any(x["id"] == "default" for x in r0.json())

    r1 = c.post(
        "/api/v1/web/sessions",
        json={"title": "New chat"},
        headers={"X-User-Id": uid},
    )
    assert r1.status_code == 200, r1.text
    created = r1.json()
    assert created["id"]
    assert created["title"] == "New chat"
    new_id = created["id"]

    r2 = c.get("/api/v1/web/sessions", headers={"X-User-Id": uid})
    assert r2.status_code == 200
    ids = {x["id"] for x in r2.json()}
    assert "default" in ids
    assert new_id in ids

    m_def = c.get(
        f"/api/v1/web/sessions/default/messages",
        headers={"X-User-Id": uid},
    )
    m_new = c.get(
        f"/api/v1/web/sessions/{new_id}/messages",
        headers={"X-User-Id": uid},
    )
    assert m_def.status_code == 200 and m_new.status_code == 200
    assert m_new.json() == []

    bad = c.get(
        "/api/v1/web/sessions/w-not-exists-ffffffffffffffffffffffffffffffff/messages",
        headers={"X-User-Id": uid},
    )
    assert bad.status_code == 404


@patch("app.core.security.get_settings")
def test_web_work_context_unknown_session_404(mock_gs) -> None:
    m = type("S", (), {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    c = TestClient(app)
    r = c.get(
        "/api/v1/web/work-context?session_id=w-not-exists-ffffffffffffffffffffffffffffff",
        headers={"X-User-Id": "web_wctx_404"},
    )
    assert r.status_code == 404


@patch("app.core.security.get_settings")
def test_web_work_context_scoped_to_session_after_create(mock_gs) -> None:
    m = type("S", (), {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    uid = "web_wctx_scoped_1"
    c = TestClient(app)
    cr = c.post(
        "/api/v1/web/sessions",
        json={"title": "Test"},
        headers={"X-User-Id": uid},
    )
    assert cr.status_code == 200, cr.text
    sid = cr.json()["id"]
    r = c.get(
        f"/api/v1/web/work-context?session_id={sid}",
        headers={"X-User-Id": uid},
    )
    assert r.status_code == 200, r.text
    assert "flow" in r.json()


@patch("app.services.web_chat_service.process_web_message")
@patch("app.core.security.get_settings")
def test_web_chat_passes_session_id_to_pipeline(mock_gs, mock_chat) -> None:
    from app.services.channel_gateway.origin_context import get_channel_origin

    m = type("S", (), {"nexa_web_api_token": "secret", "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    seen_origin: dict = {}

    def _web_capture(db, uid, text, **kw):
        seen_origin.update(dict(get_channel_origin() or {}))
        return WebChatResult(
            reply="x",
            intent="chat",
            agent_key="nexa",
            decision_summary={
                "agent": "nexa",
                "action": "chat_response",
                "tool": "llm",
                "reason": "Nexa used the general chat path for this message.",
                "risk": "low",
                "approval_required": False,
            },
        )

    mock_chat.side_effect = _web_capture
    c = TestClient(app)
    c.post(
        "/api/v1/web/chat",
        json={"message": "hi", "session_id": "w-abc123"},
        headers={"X-User-Id": "web_x", "Authorization": "Bearer secret"},
    )
    assert mock_chat.called
    _args, kwargs = mock_chat.call_args
    assert kwargs.get("web_session_id") == "w-abc123"
    assert seen_origin.get("channel") == "web"
    assert seen_origin.get("web_session_id") == "w-abc123"


@patch("app.core.security.get_settings")
def test_web_session_messages_stay_isolated_in_db(mock_gs) -> None:
    m = type("S", (), {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    uid = "web_iso_1"
    c = TestClient(app)
    cr = c.post(
        "/api/v1/web/sessions",
        json={"title": "B"},
        headers={"X-User-Id": uid},
    )
    new_id = cr.json()["id"]
    # Direct DB: put one user line in "default" and a different one in the new session
    db = SessionLocal()
    try:
        a = db.scalars(
            select(ConversationContext).where(
                ConversationContext.user_id == uid,
                ConversationContext.session_id == "default",
            )
        ).first()
        b = db.scalars(
            select(ConversationContext).where(
                ConversationContext.user_id == uid, ConversationContext.session_id == new_id
            )
        ).first()
        assert a is not None and b is not None
        a.recent_messages_json = json.dumps(
            [{"role": "user", "text": "only default", "ts": "1"}]
        )
        b.recent_messages_json = json.dumps(
            [{"role": "user", "text": "only new", "ts": "2"}]
        )
        db.add(a)
        db.add(b)
        db.commit()
    finally:
        db.close()

    m_def = c.get("/api/v1/web/sessions/default/messages", headers={"X-User-Id": uid})
    m_new = c.get(f"/api/v1/web/sessions/{new_id}/messages", headers={"X-User-Id": uid})
    assert m_def.status_code == 200 and m_new.status_code == 200
    t1 = m_def.json()
    t2 = m_new.json()
    assert len(t1) == 1 and t1[0]["content"] == "only default"
    assert len(t2) == 1 and t2[0]["content"] == "only new"


@patch("app.core.security.get_settings")
def test_web_delete_secondary_session(mock_gs) -> None:
    m = type("S", (), {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    uid = "web_del_secondary_1"
    c = TestClient(app)
    cr = c.post(
        "/api/v1/web/sessions",
        json={"title": "To delete"},
        headers={"X-User-Id": uid},
    )
    assert cr.status_code == 200, cr.text
    new_id = cr.json()["id"]

    d = c.delete(f"/api/v1/web/sessions/{new_id}", headers={"X-User-Id": uid})
    assert d.status_code == 204, d.text

    r = c.get("/api/v1/web/sessions", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert new_id not in {x["id"] for x in r.json()}


@patch("app.core.security.get_settings")
def test_web_delete_default_clears_messages(mock_gs) -> None:
    m = type("S", (), {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    uid = "web_del_main_1"
    c = TestClient(app)
    c.get("/api/v1/web/sessions", headers={"X-User-Id": uid})

    db = SessionLocal()
    try:
        row = db.scalars(
            select(ConversationContext).where(
                ConversationContext.user_id == uid,
                ConversationContext.session_id == "default",
            )
        ).first()
        assert row is not None
        row.recent_messages_json = json.dumps(
            [{"role": "user", "text": "before clear", "ts": "1"}]
        )
        db.add(row)
        db.commit()
    finally:
        db.close()

    before = c.get("/api/v1/web/sessions/default/messages", headers={"X-User-Id": uid})
    assert before.status_code == 200
    assert len(before.json()) == 1

    d = c.delete("/api/v1/web/sessions/default", headers={"X-User-Id": uid})
    assert d.status_code == 204, d.text

    after = c.get("/api/v1/web/sessions/default/messages", headers={"X-User-Id": uid})
    assert after.status_code == 200
    assert after.json() == []

    listed = c.get("/api/v1/web/sessions", headers={"X-User-Id": uid})
    assert listed.status_code == 200
    assert any(x["id"] == "default" for x in listed.json())


@patch("app.core.security.get_settings")
def test_web_delete_session_unknown_404(mock_gs) -> None:
    m = type("S", (), {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    c = TestClient(app)
    r = c.delete(
        "/api/v1/web/sessions/w-not-exists-ffffffffffffffffffffffffffffffff",
        headers={"X-User-Id": "web_del_404"},
    )
    assert r.status_code == 404
