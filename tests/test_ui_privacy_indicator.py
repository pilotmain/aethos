"""Privacy indicator derivation for Mission Control UI (Phase 13)."""

from __future__ import annotations

from app.services.mission_control.nexa_next_state import derive_privacy_indicator


def test_privacy_indicator_safe_when_empty() -> None:
    assert derive_privacy_indicator([])["level"] == "safe"


def test_privacy_indicator_redacted() -> None:
    ev = [{"type": "pii_redacted", "data": {"pii": True}}]
    assert derive_privacy_indicator(ev)["level"] == "redacted"


def test_privacy_indicator_blocked_secret() -> None:
    ev = [{"type": "secret_blocked"}]
    assert derive_privacy_indicator(ev)["level"] == "blocked"


def test_privacy_indicator_blocked_beats_redacted() -> None:
    ev = [
        {"type": "pii_redacted"},
        {"type": "pii_blocked_by_policy"},
    ]
    assert derive_privacy_indicator(ev)["level"] == "blocked"


def test_state_endpoint_includes_privacy_indicator() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    r = c.get("/api/v1/mission-control/state")
    assert r.status_code == 200
    pi = r.json().get("privacy_indicator") or {}
    assert pi.get("level") in ("safe", "redacted", "blocked")
