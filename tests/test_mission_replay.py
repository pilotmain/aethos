"""Phase 10 — replay stored mission input through the gateway."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.models.nexa_next_runtime import NexaMission, NexaMissionTask


def test_replay_mission_with_stored_input(api_client, db_session):
    client: TestClient
    client, uid = api_client

    mid = uuid.uuid4().hex[:24]
    inp = "@analyst: forecast market trends for robotics adoption over the next year"
    db_session.add(
        NexaMission(
            id=mid,
            user_id=uid,
            title="Replay fixture",
            status="completed",
            input_text=inp,
        )
    )
    # Mission Control purges mission rows with no tasks (see purge_scheme_impostor_tasks).
    db_session.add(
        NexaMissionTask(
            mission_id=mid,
            agent_handle="analyst",
            role="analyst",
            task=inp[:2000],
            status="completed",
        )
    )
    db_session.commit()

    st = client.get("/api/v1/mission-control/state", headers={"X-User-Id": uid})
    assert st.status_code == 200
    missions = st.json().get("missions") or []
    assert any(m.get("id") == mid for m in missions)
    row = next(m for m in missions if m.get("id") == mid)
    assert row.get("input_text")

    rep = client.post(f"/api/v1/mission-control/replay/{mid}", headers={"X-User-Id": uid})
    assert rep.status_code == 200
    body = rep.json()
    assert isinstance(body, dict)
    assert body.get("mode") == "chat" or body.get("text") or body.get("ok") is not None


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
