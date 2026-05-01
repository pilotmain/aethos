"""Phase 10 — replay stored mission input through the gateway."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_replay_mission_with_stored_input(api_client):
    client: TestClient
    client, uid = api_client

    run = client.post(
        "/api/v1/mission-control/gateway/run",
        json={
            "text": "@analyst: forecast market trends for robotics adoption over the next year",
            "user_id": uid,
        },
    )
    assert run.status_code == 200

    st = client.get("/api/v1/mission-control/state", headers={"X-User-Id": uid})
    assert st.status_code == 200
    missions = st.json().get("missions") or []
    assert missions
    mid = missions[0]["id"]
    assert missions[0].get("input_text")

    rep = client.post(f"/api/v1/mission-control/replay/{mid}")
    assert rep.status_code == 200
    body = rep.json()
    assert body.get("status") == "completed"


def test_admin_endpoints_404_when_disabled(api_client, monkeypatch):
    client, _uid = api_client
    monkeypatch.setenv("NEXA_ADMIN_ENDPOINTS_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        r = client.get("/api/v1/admin/privacy/events")
        assert r.status_code == 404
    finally:
        monkeypatch.delenv("NEXA_ADMIN_ENDPOINTS_ENABLED", raising=False)
        get_settings.cache_clear()


def test_admin_privacy_visible_when_enabled(api_client, monkeypatch):
    client, _uid = api_client
    monkeypatch.setenv("NEXA_ADMIN_ENDPOINTS_ENABLED", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        r = client.get("/api/v1/admin/privacy/events")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
    finally:
        monkeypatch.delenv("NEXA_ADMIN_ENDPOINTS_ENABLED", raising=False)
        get_settings.cache_clear()
