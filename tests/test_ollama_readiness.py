# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Ollama readiness gates ``providers_available()`` (no real Ollama required)."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.llm.bootstrap import clear_ollama_readiness_cache
from app.services.llm.completion import providers_available
from app.services.llm_key_resolution import MergedLlmKeyInfo


@pytest.fixture(autouse=True)
def _clear_ollama_cache():
    clear_ollama_readiness_cache()
    yield
    clear_ollama_readiness_cache()


def test_providers_available_false_when_ollama_only_and_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    base = get_settings()
    fake = base.model_copy(
        update={
            "nexa_ollama_enabled": True,
            "nexa_llm_provider": "auto",
            "anthropic_api_key": "",
            "openai_api_key": "",
            "deepseek_api_key": "",
            "openrouter_api_key": "",
            "nexa_llm_api_key": "",
        }
    )
    monkeypatch.setattr("app.services.llm.completion.get_settings", lambda: fake)
    monkeypatch.setattr(
        "app.services.llm_key_resolution.get_merged_api_keys",
        lambda: MergedLlmKeyInfo(anthropic_api_key=None, openai_api_key=None),
    )
    monkeypatch.setattr("app.services.llm.bootstrap.is_ollama_ready", lambda: False)
    assert providers_available() is False


def test_providers_available_true_when_ollama_only_and_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    base = get_settings()
    fake = base.model_copy(
        update={
            "nexa_ollama_enabled": True,
            "nexa_llm_provider": "auto",
            "anthropic_api_key": "",
            "openai_api_key": "",
            "deepseek_api_key": "",
            "openrouter_api_key": "",
            "nexa_llm_api_key": "",
        }
    )
    monkeypatch.setattr("app.services.llm.completion.get_settings", lambda: fake)
    monkeypatch.setattr(
        "app.services.llm_key_resolution.get_merged_api_keys",
        lambda: MergedLlmKeyInfo(anthropic_api_key=None, openai_api_key=None),
    )
    monkeypatch.setattr("app.services.llm.bootstrap.is_ollama_ready", lambda: True)
    assert providers_available() is True


def test_providers_available_true_with_cloud_key_ignores_ollama_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    base = get_settings()
    fake = base.model_copy(
        update={
            "nexa_ollama_enabled": True,
            "nexa_llm_provider": "auto",
            "anthropic_api_key": "sk-ant-test-placeholder-for-gate",
            "openai_api_key": "",
            "deepseek_api_key": "",
            "openrouter_api_key": "",
            "nexa_llm_api_key": "",
        }
    )
    monkeypatch.setattr("app.services.llm.completion.get_settings", lambda: fake)
    monkeypatch.setattr(
        "app.services.llm_key_resolution.get_merged_api_keys",
        lambda: MergedLlmKeyInfo(
            anthropic_api_key="sk-ant-test-placeholder-for-gate", openai_api_key=None
        ),
    )

    def _boom() -> bool:
        raise AssertionError("is_ollama_ready should not run when cloud keys satisfy providers_available")

    monkeypatch.setattr("app.services.llm.bootstrap.is_ollama_ready", _boom)
    assert providers_available() is True
