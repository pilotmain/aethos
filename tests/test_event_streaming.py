"""Phase 7 — streamable bus, timeline API, WebSocket delivery."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.events.bus import clear_events, list_events, publish


def test_publish_appends_to_timeline() -> None:
    clear_events()
    publish({"type": "unit.test", "n": 1})
    assert list_events()[-1]["type"] == "unit.test"


def test_timeline_http_returns_events() -> None:
    clear_events()
    publish({"type": "timeline_probe"})
    client = TestClient(app)
    r = client.get("/api/v1/mission-control/events/timeline")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert body[-1]["type"] == "timeline_probe"


def test_events_stream_alias_matches_timeline() -> None:
    clear_events()
    publish({"type": "stream_alias"})
    client = TestClient(app)
    t = client.get("/api/v1/mission-control/events/timeline").json()
    s = client.get("/api/v1/mission-control/events/stream").json()
    assert t == s


def test_websocket_receives_published_event() -> None:
    clear_events()
    client = TestClient(app)
    with client.websocket_connect("/api/v1/mission-control/events/ws") as ws:
        publish({"type": "ws_delivery", "ok": True})
        data = ws.receive_json()
        assert data["type"] == "ws_delivery"
        assert data["ok"] is True
