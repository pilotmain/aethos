"""Phase 7 / 15 — streamable bus, timeline API, WebSocket delivery, normalized schema."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.events.bus import clear_events, list_events, publish


def test_publish_appends_to_timeline() -> None:
    clear_events()
    publish({"type": "unit.test", "payload": {"n": 1}})
    row = list_events()[-1]
    assert row["type"] == "unit.test"
    assert row["payload"]["n"] == 1
    assert "timestamp" in row
    assert "mission_id" in row and "agent" in row


def test_timeline_http_returns_events() -> None:
    clear_events()
    publish({"type": "timeline_probe", "payload": {}})
    client = TestClient(app)
    r = client.get("/api/v1/mission-control/events/timeline")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert body[-1]["type"] == "timeline_probe"


def test_websocket_receives_published_event() -> None:
    clear_events()
    client = TestClient(app)
    with client.websocket_connect("/api/v1/mission-control/events/ws") as ws:
        publish({"type": "ws_delivery", "payload": {"ok": True}})
        data = ws.receive_json()
        assert data["type"] == "ws_delivery"
        assert data["payload"]["ok"] is True
