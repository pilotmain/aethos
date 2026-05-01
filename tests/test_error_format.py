"""Phase 28 — JSON error envelope from global exception handlers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_not_found_error_envelope() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/no-such-route-phase28-error-test")
    assert r.status_code == 404
    body = r.json()
    assert body.get("ok") is False
    assert body.get("code") == "NOT_FOUND"
    assert isinstance(body.get("error"), str)


def test_gone_memory_legacy_envelope() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/memory", headers={"X-User-Id": "web_phase28_err"})
    assert r.status_code == 410
    body = r.json()
    assert body.get("ok") is False
    assert body.get("code") == "GONE"


def test_validation_error_envelope() -> None:
    c = TestClient(app)
    r = c.post("/api/v1/web/chat", json={"not": "valid"}, headers={"X-User-Id": "web_phase28_val"})
    assert r.status_code == 422
    body = r.json()
    assert body.get("ok") is False
    assert body.get("code") == "VALIDATION_ERROR"
    assert isinstance(body.get("error"), str)
