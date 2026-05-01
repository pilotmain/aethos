"""Provider transparency roll-ups (Phase 13)."""

from __future__ import annotations

from app.services.mission_control.nexa_next_state import summarize_provider_transparency


def test_summarize_counts_providers() -> None:
    prov = [
        {"provider": "openai", "status": "completed", "agent": "a1"},
        {"provider": "openai", "status": "blocked", "agent": "a1"},
        {"provider": "local_stub", "status": "fallback", "agent": "a2", "fallback_from": "anthropic"},
    ]
    priv = [{"type": "pii_redacted"}]
    out = summarize_provider_transparency(prov, privacy_events=priv)
    assert out["privacy_redactions_observed"] == 1
    assert "openai" in out["by_provider"]
    assert out["by_provider"]["openai"]["calls"] == 2
    assert out["by_provider"]["openai"]["blocked"] == 1


def test_state_has_provider_transparency() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    r = c.get("/api/v1/mission-control/state", headers={"X-User-Id": "web_prov_transparency"})
    assert r.status_code == 200
    pt = r.json().get("provider_transparency") or {}
    assert "by_provider" in pt
