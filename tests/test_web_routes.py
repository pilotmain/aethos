# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.web_ui import WebResponseSourceItem
from app.services.web_chat_service import WebChatResult


def test_web_sessions_unauthorized_without_user_header():
    c = TestClient(app)
    r = c.get("/api/v1/web/sessions")
    assert r.status_code == 401


@patch("app.core.security.get_settings")
def test_web_sessions_list_ok(mock_gs):
    m = type("S", (), {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m

    c = TestClient(app)
    r = c.get(
        "/api/v1/web/sessions",
        headers={"X-User-Id": "web_smoke_1"},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["id"] == "default"
    assert "message_count" in data[0] and "preview" in data[0]


@patch("app.core.security.get_settings")
@patch("app.api.routes.web.build_nexa_doctor_text", side_effect=RuntimeError("simulated doctor build failure"))
def test_web_system_doctor_returns_200_on_build_failure(_mock_build, mock_gs):
    m = type("S", (), {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    c = TestClient(app)
    r = c.get(
        "/api/v1/web/system/doctor",
        headers={"X-User-Id": "web_smoke_1"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "text" in data
    assert "RuntimeError" in data["text"] or "partial" in data["text"].lower()


@patch("app.services.web_chat_service.process_web_message")
@patch("app.core.security.get_settings")
def test_web_chat_mocked(mock_gs, mock_chat):
    m = type("S", (), {"nexa_web_api_token": "secret", "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    mock_chat.return_value = WebChatResult(
        reply="hi",
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

    c = TestClient(app)
    r = c.post(
        "/api/v1/web/chat",
        json={"message": "hello"},
        headers={"X-User-Id": "web_x", "Authorization": "Bearer secret"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["reply"] == "hi"
    assert data.get("sources") == []
    assert data.get("response_kind") in (None, "chat")
    d = data.get("decision_summary")
    assert d and d.get("agent") == "nexa" and d.get("reason")


@patch("app.services.web_chat_service.process_web_message")
@patch("app.core.security.get_settings")
def test_web_chat_includes_web_search_kind(mock_gs, mock_chat):
    m = type("S", (), {"nexa_web_api_token": "secret", "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    mock_chat.return_value = WebChatResult(
        reply="x",
        intent="q",
        agent_key="research",
        response_kind="web_search",
        sources=[WebResponseSourceItem(url="https://u.io/", title="T")],
    )
    c = TestClient(app)
    r = c.post(
        "/api/v1/web/chat",
        json={"message": "x"},
        headers={"X-User-Id": "web_x", "Authorization": "Bearer secret"},
    )
    j = r.json()
    assert j["response_kind"] == "web_search"
    assert j["sources"][0]["url"] == "https://u.io/"


@patch("app.services.web_chat_service.process_web_message")
@patch("app.core.security.get_settings")
def test_web_chat_includes_sources_when_set(mock_gs, mock_chat):
    m = type("S", (), {"nexa_web_api_token": "secret", "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    mock_chat.return_value = WebChatResult(
        reply="body",
        intent="q",
        agent_key="research",
        related_job_ids=[],
        response_kind="public_web",
        sources=[WebResponseSourceItem(url="https://a.io/", title=None)],
    )
    c = TestClient(app)
    r = c.post(
        "/api/v1/web/chat",
        json={"message": "x"},
        headers={"X-User-Id": "web_x", "Authorization": "Bearer secret"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["response_kind"] == "public_web"
    assert j["sources"][0]["url"] == "https://a.io/"


@patch("app.services.web_chat_service.process_web_message")
@patch("app.core.security.get_settings")
def test_web_chat_marketing_includes_response_kind_and_tool_line(mock_gs, mock_chat) -> None:
    m = type("S", (), {"nexa_web_api_token": "secret", "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    mock_chat.return_value = WebChatResult(
        reply="m",
        intent="general",
        agent_key="marketing",
        response_kind="marketing_web_analysis",
        sources=[WebResponseSourceItem(url="https://pilotmain.com/", title="P")],
        web_tool_line="Tool: Public web read + Web search",
        decision_summary={
            "agent": "marketing",
            "action": "marketing_web_analysis",
            "tool": "marketing_web_tools",
            "reason": "x",
            "risk": "low",
            "approval_required": False,
        },
    )
    c = TestClient(app)
    r = c.post(
        "/api/v1/web/chat",
        json={"message": "x"},
        headers={"X-User-Id": "web_x", "Authorization": "Bearer secret"},
    )
    j = r.json()
    assert j["response_kind"] == "marketing_web_analysis"
    assert (j.get("web_tool_line") or "").startswith("Tool:")
    assert "Public web read" in (j.get("web_tool_line") or "")
    assert "pilotmain.com" in j["sources"][0]["url"]


@patch("app.core.security.get_settings")
def test_web_usage_summary_ok(mock_gs):
    m = type("S", (), {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    c = TestClient(app)
    r = c.get(
        "/api/v1/web/usage/summary",
        headers={"X-User-Id": "web_smoke_1"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert "total_calls" in j
    assert "estimated_cost_usd" in j
    assert "by_provider" in j


@patch("app.core.security.get_settings")
def test_web_usage_recent_ok(mock_gs):
    m = type("S", (), {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    c = TestClient(app)
    r = c.get(
        "/api/v1/web/usage/recent?limit=5",
        headers={"X-User-Id": "web_smoke_1"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert "items" in j
    assert isinstance(j["items"], list)


@patch("app.core.security.get_settings")
def test_web_system_status_includes_web_access_flags(mock_gs):
    m = type(
        "S",
        (),
        {
            "nexa_web_api_token": None,
            "nexa_web_origins": "http://localhost:3000",
        },
    )()
    mock_gs.return_value = m
    c = TestClient(app)
    r = c.get("/api/v1/web/system/status", headers={"X-User-Id": "web_smoke_1"})
    assert r.status_code == 200, r.text
    ids = {x["id"] for x in r.json().get("indicators", [])}
    assert "public_web" in ids
    assert "browser_preview" in ids
    assert "web_search" in ids


@patch("app.core.security.get_settings")
def test_web_documents_list_ok(mock_gs):
    m = type("S", (), {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    c = TestClient(app)
    r = c.get(
        "/api/v1/web/documents?limit=5",
        headers={"X-User-Id": "web_docs_1"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert isinstance(j, list)


def test_web_chat_invalid_x_user_id_returns_400():
    c = TestClient(app)
    bad = "tg_8666826080:AAG_faketoken_paste"
    r = c.post(
        "/api/v1/web/chat",
        json={"message": "hello"},
        headers={"X-User-Id": bad},
    )
    assert r.status_code == 400, r.text
    j = r.json()
    assert "Invalid Web User ID" in (j.get("detail") or "")
    assert "AAG" not in r.text


def test_web_me_invalid_x_user_id_returns_400():
    c = TestClient(app)
    r = c.get(
        "/api/v1/web/me",
        headers={"X-User-Id": "x"},
    )
    assert r.status_code == 400
    j = r.json()
    assert "Invalid Web User ID" in (j.get("detail") or "")


@patch("app.core.security.get_settings")
def test_web_me_valid_tg_ok(mock_gs):
    m = type("S", (), {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"})()
    mock_gs.return_value = m
    c = TestClient(app)
    r = c.get(
        "/api/v1/web/me",
        headers={"X-User-Id": "tg_123456789"},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("app_user_id") == "tg_123456789"
