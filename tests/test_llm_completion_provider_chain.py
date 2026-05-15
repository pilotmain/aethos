# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Provider chain construction: Ollama-primary cloud failover and local-first auto."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.llm.completion import _build_chain


def _settings(**kwargs: object) -> MagicMock:
    base = dict(
        nexa_llm_provider="auto",
        nexa_llm_fallback_providers="",
        nexa_cost_aware_enabled=False,
        nexa_pure_local_llm_mode=False,
        nexa_local_first=False,
        nexa_cost_aware_fallback_provider="",
    )
    base.update(kwargs)
    s = MagicMock()
    for k, v in base.items():
        setattr(s, k, v)
    return s


def _registry(registered: set[str]) -> MagicMock:
    reg = MagicMock()
    reg.get_provider = lambda name: object() if name in registered else None
    return reg


def test_explicit_ollama_primary_appends_cloud_in_auto_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ollama-only primary must still try Anthropic/OpenAI when local fails."""
    reg = _registry({"ollama", "anthropic", "openai"})
    monkeypatch.setattr(
        "app.services.llm.completion.get_settings",
        lambda: _settings(nexa_llm_provider="ollama"),
    )
    monkeypatch.setattr("app.services.llm.completion.get_llm_registry", lambda: reg)
    assert _build_chain() == ["ollama", "anthropic", "openai"]


def test_local_first_auto_puts_ollama_before_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    reg = _registry({"anthropic", "ollama"})
    monkeypatch.setattr(
        "app.services.llm.completion.get_settings",
        lambda: _settings(nexa_llm_provider="auto", nexa_local_first=True),
    )
    monkeypatch.setattr("app.services.llm.completion.get_llm_registry", lambda: reg)
    assert _build_chain() == ["ollama", "anthropic"]


def test_auto_without_local_first_keeps_vendor_order(monkeypatch: pytest.MonkeyPatch) -> None:
    reg = _registry({"anthropic", "ollama"})
    monkeypatch.setattr(
        "app.services.llm.completion.get_settings",
        lambda: _settings(nexa_llm_provider="auto", nexa_local_first=False),
    )
    monkeypatch.setattr("app.services.llm.completion.get_llm_registry", lambda: reg)
    assert _build_chain() == ["anthropic", "ollama"]
