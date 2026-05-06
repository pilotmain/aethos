"""Phase 35 — REST agent spawn / list / status under /api/v1/agents."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import get_valid_web_user_id
from app.main import app
from app.services.sub_agent_registry import AgentRegistry


def test_agent_spawn_list_status(monkeypatch: pytest.MonkeyPatch) -> None:
    uid = "web_agent_spawn_test"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    monkeypatch.setenv("NEXA_AGENT_ORCHESTRATION_ENABLED", "true")
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
    get_settings.cache_clear()
    AgentRegistry.reset()
    c = TestClient(app)
    try:
        r = c.post(
            "/api/v1/agents/spawn",
            headers={"X-User-Id": uid},
            json={"name": "qa_agent", "domain": "qa"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert body.get("agent", {}).get("name") == "qa_agent"

        dup = c.post(
            "/api/v1/agents/spawn",
            headers={"X-User-Id": uid},
            json={"name": "qa_agent", "domain": "qa"},
        )
        assert dup.status_code == 200
        assert "already exists" in (dup.json().get("message") or "")

        lst = c.get("/api/v1/agents/list", headers={"X-User-Id": uid})
        assert lst.status_code == 200
        agents = lst.json().get("agents") or []
        assert len(agents) >= 1
        assert agents[0].get("name") == "qa_agent"

        st = c.get("/api/v1/agents/status/qa_agent", headers={"X-User-Id": uid})
        assert st.status_code == 200
        assert st.json().get("agent", {}).get("domain") == "qa"

        missing = c.get("/api/v1/agents/status/nope_nope", headers={"X-User-Id": uid})
        assert missing.status_code == 404

        ex = c.post(
            "/api/v1/agents/execute/qa_agent",
            headers={"X-User-Id": uid},
            json={"task": "security scan ."},
        )
        assert ex.status_code == 200, ex.text
        assert ex.json().get("ok") is True
        assert "result" in ex.json()
    finally:
        app.dependency_overrides.clear()
        AgentRegistry.reset()
        monkeypatch.delenv("NEXA_AGENT_ORCHESTRATION_ENABLED", raising=False)
        get_settings.cache_clear()


def test_agent_spawn_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    uid = "web_agent_spawn_off"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    monkeypatch.setenv("NEXA_AGENT_ORCHESTRATION_ENABLED", "false")
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
    get_settings.cache_clear()
    c = TestClient(app)
    try:
        r = c.post(
            "/api/v1/agents/spawn",
            headers={"X-User-Id": uid},
            json={"name": "x", "domain": "git"},
        )
        assert r.status_code == 503
    finally:
        app.dependency_overrides.clear()
        monkeypatch.delenv("NEXA_AGENT_ORCHESTRATION_ENABLED", raising=False)
        get_settings.cache_clear()
