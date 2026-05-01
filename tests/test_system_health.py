"""Phase 11 — system health + metrics routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_system_health_ok() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/system/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert body["db"] == "connected"
    assert body["providers"]
    assert "uptime_seconds" in body
    assert body["version"]


def test_system_metrics_snapshot() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/system/metrics")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)


def test_security_headers_on_api_response() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/health")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"


def test_validation_error_shape() -> None:
    """Unhandled routes still use HTTP handler; invalid body uses validation handler."""
    c = TestClient(app)
    r = c.get("/api/v1/no-such-route-phase11-test")
    assert r.status_code == 404
    body = r.json()
    assert body.get("ok") is False
    assert body.get("code") == "NOT_FOUND"
    assert "error" in body
