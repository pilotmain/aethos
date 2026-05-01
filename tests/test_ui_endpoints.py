"""Smoke tests for Mission Control JSON endpoints used by the web UI (Phase 12)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_mission_control_graph_shape() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/mission-control/graph", headers={"X-User-Id": "web_mc_ui_test"})
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body and isinstance(body["nodes"], list)
    assert "edges" in body and isinstance(body["edges"], list)


def test_mission_control_state_shape() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/mission-control/state", headers={"X-User-Id": "web_mc_ui_test"})
    assert r.status_code == 200
    body = r.json()
    for key in (
        "missions",
        "tasks",
        "artifacts",
        "events",
        "privacy_indicator",
        "provider_transparency",
        "integrity_alerts",
        "metrics",
        "runtime",
        "agent_performance",
    ):
        assert key in body


def test_mission_control_events_timeline_is_list() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/mission-control/events/timeline")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_mission_control_state_requires_user_header() -> None:
    """Mission Control state — requires ``X-User-Id`` like the browser."""
    c = TestClient(app)
    r = c.get("/api/v1/mission-control/state")
    assert r.status_code == 401


def test_mission_control_summary_returns_gone() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/mission-control/summary", headers={"X-User-Id": "web_mc_ui_test"})
    assert r.status_code == 410


def test_mission_control_state_ok_with_dev_user_header() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/mission-control/state", headers={"X-User-Id": "web_mc_ui_test"})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "missions" in body and "overview" in body
