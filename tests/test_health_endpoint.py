"""Phase 28 — system health production fields."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_system_health_includes_readiness_fields() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/system/health")
    assert r.status_code == 200
    body = r.json()
    assert "ok" in body and isinstance(body["ok"], bool)
    assert body["db"] == "connected"
    assert body.get("scheduler") in ("running", "unknown")
    assert body.get("privacy_mode") in ("standard", "strict")
    assert body.get("runtime") in ("ready", "degraded")
