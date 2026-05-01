"""Phase 42 — Discord bot helpers (no live Discord network)."""

from __future__ import annotations

import pytest

from app.services.channels.discord_bot import _resolve_app_user_id


def test_resolve_app_user_id_prefers_fixed_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_DISCORD_APP_USER_ID", "owner_fixed")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert _resolve_app_user_id("999") == "owner_fixed"
    finally:
        monkeypatch.delenv("NEXA_DISCORD_APP_USER_ID", raising=False)
        get_settings.cache_clear()


def test_resolve_app_user_id_fallback_discord_prefix() -> None:
    assert _resolve_app_user_id("12345").startswith("discord:")
