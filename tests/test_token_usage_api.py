"""Phase 38 — GET /api/v1/providers/usage."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_providers_usage_requires_auth() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/providers/usage")
    assert r.status_code == 401


def test_providers_usage_returns_safe_summary(api_client) -> None:
    client, _uid = api_client
    r = client.get("/api/v1/providers/usage")
    assert r.status_code == 200
    data = r.json()
    assert "calls" in data and isinstance(data["calls"], list)
    assert "summary" in data and isinstance(data["summary"], dict)
