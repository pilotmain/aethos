"""Phase 52C — region-based catalog + router defaults."""

from __future__ import annotations

from app.services.providers.catalog import choose_provider_for_task, providers_by_region


def test_local_first_defaults_to_ollama() -> None:
    assert choose_provider_for_task(local_first=True, user_settings={}) == "ollama"


def test_preferred_provider_overrides_local_first() -> None:
    assert choose_provider_for_task(
        local_first=True,
        user_settings={"preferred_provider": "openai"},
    ) == "openai"


def test_china_region_list_includes_deepseek() -> None:
    cn = providers_by_region("china")
    assert any(p.id == "deepseek" for p in cn)
