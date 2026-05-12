# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 14 — Mission Control events WebSocket delivers bus events to a single subscriber stream."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.events.bus import clear_events, publish


def test_mission_control_events_ws_delivers_json_events() -> None:
    clear_events()
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/mission-control/events/ws") as ws:
            publish(
                {
                    "type": "task.started",
                    "timestamp": "2026-05-01T00:00:00Z",
                    "mission_id": "m1",
                    "agent": "alpha",
                    "payload": {"step": 1},
                }
            )
            body = ws.receive_json()
            assert body["type"] == "task.started"
            assert body["mission_id"] == "m1"
            assert body["payload"] == {"step": 1}


def test_mission_control_events_ws_accepts_client_ping() -> None:
    """Client keepalive text should not tear down the socket."""
    clear_events()
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/mission-control/events/ws") as ws:
            ws.send_text("ping")
            publish({"type": "noop.test", "payload": {}})
            body = ws.receive_json()
            assert body["type"] == "noop.test"
