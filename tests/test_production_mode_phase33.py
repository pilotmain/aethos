"""Phase 33 — NEXA_PRODUCTION_MODE tightens runtime posture."""

from __future__ import annotations

from app.core.config import Settings, get_settings


def test_production_mode_env(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_PRODUCTION_MODE", "true")
    get_settings.cache_clear()
    s = get_settings()
    assert s.nexa_production_mode is True
    assert s.debug is False
    assert s.nexa_agent_tools_enabled is False
    assert s.nexa_browser_preview_enabled is False
    get_settings.cache_clear()


def test_development_default(monkeypatch) -> None:
    monkeypatch.delenv("NEXA_PRODUCTION_MODE", raising=False)
    get_settings.cache_clear()
    s = Settings()
    assert s.nexa_production_mode is False
