"""Phase 27 — deprecated REST aliases removed or return HTTP 410."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_mission_control_summary_gone() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/mission-control/summary", headers={"X-User-Id": "x"})
    assert r.status_code == 410


def test_agents_alias_removed() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/agents", headers={"X-User-Id": "x"})
    assert r.status_code == 404
