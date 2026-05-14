# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deterministic smoke: USE_REAL_LLM intent without any registered provider (no keys, no Ollama)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from app.services.llm_key_resolution import MergedLlmKeyInfo


def _assert_no_remote_llm(*_a: Any, **_kw: Any) -> None:
    raise AssertionError("no-provider smoke must not call remote LLM completion APIs")


@pytest.fixture
def no_provider_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate USE_REAL_LLM=true with no Anthropic/OpenAI merge and no other provider."""
    from app.core.config import get_settings as _real_get_settings

    def _settings_use_real_true() -> Any:
        return _real_get_settings().model_copy(update={"use_real_llm": True})

    monkeypatch.setattr("app.services.intent_classifier.get_settings", _settings_use_real_true)
    monkeypatch.setattr("app.services.response_composer.get_settings", _settings_use_real_true)

    monkeypatch.setattr(
        "app.services.llm_key_resolution.get_merged_api_keys",
        lambda: MergedLlmKeyInfo(anthropic_api_key=None, openai_api_key=None),
    )
    monkeypatch.setattr("app.services.response_composer.providers_available", lambda: False)

    monkeypatch.setattr("app.services.intent_classifier.safe_llm_json_call", _assert_no_remote_llm)
    monkeypatch.setattr("app.services.response_composer.primary_complete_messages", _assert_no_remote_llm)


def test_intent_uses_fallback_without_merged_keys(no_provider_llm_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.intent_classifier import classify_intent_fallback, classify_intent_llm, get_intent

    calls: list[str] = []

    def _spy_fallback(msg: str, conversation_snapshot: dict | None = None) -> dict:
        calls.append("fallback")
        return classify_intent_fallback(msg, conversation_snapshot)

    monkeypatch.setattr("app.services.intent_classifier.classify_intent_fallback", _spy_fallback)

    msg = "buy milk, call dentist, finish the quarterly report"
    direct = classify_intent_llm(msg)
    assert calls == ["fallback"]
    assert direct["intent"] == "brain_dump"

    calls.clear()
    assert get_intent(msg) == "brain_dump"
    assert calls == ["fallback"]


def test_build_response_composer_fallback_without_providers(
    no_provider_llm_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.legacy_behavior_utils import Context, build_response, map_intent_to_behavior
    from app.services.response_composer import fallback_compose_response

    fb_calls: list[str] = []

    real_fb: Callable[..., Any] = fallback_compose_response

    def _spy_fb(*args: Any, **kwargs: Any) -> Any:
        fb_calls.append("fallback_compose")
        return real_fb(*args, **kwargs)

    monkeypatch.setattr("app.services.response_composer.fallback_compose_response", _spy_fb)

    ctx = Context(user_id="pytest-no-provider", tasks=[], last_plan=[], memory={})
    text = "buy milk, call dentist, finish the quarterly report"
    intent = "brain_dump"
    assert map_intent_to_behavior(intent, ctx) == "reduce"

    body = build_response(text, intent, ctx)
    assert fb_calls == ["fallback_compose"]
    assert isinstance(body, str)
    assert len(body.strip()) > 20
