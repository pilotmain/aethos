# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""``NEXA_PURE_LOCAL_LLM_MODE`` — Ollama-first intent + composer behavior."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.intent_classifier import get_intent
from app.services.response_composer import ResponseContext, compose_response


def test_pure_mode_skips_greeting_fast_path(monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings().model_copy(update={"nexa_pure_local_llm_mode": True, "use_real_llm": True})
    monkeypatch.setattr("app.services.intent_classifier.get_settings", lambda: s)
    monkeypatch.setattr("app.services.llm.completion.providers_available", lambda: True)

    called: dict[str, int] = {"n": 0}

    def _fake_llm(*_a, **_kw):
        called["n"] += 1
        return {"intent": "greeting", "confidence": 0.9, "reason": "test"}

    monkeypatch.setattr("app.services.intent_classifier.classify_intent_llm", _fake_llm)
    assert get_intent("hi") == "greeting"
    assert called["n"] == 1


def test_pure_mode_off_keeps_greeting_fast_path(monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings().model_copy(update={"nexa_pure_local_llm_mode": False, "use_real_llm": True})
    monkeypatch.setattr("app.services.intent_classifier.get_settings", lambda: s)

    called: dict[str, int] = {"n": 0}

    def _fake_llm(*_a, **_kw):
        called["n"] += 1
        return {"intent": "general_chat", "confidence": 0.5, "reason": "should not run"}

    monkeypatch.setattr("app.services.intent_classifier.classify_intent_llm", _fake_llm)
    assert get_intent("hi") == "greeting"
    assert called["n"] == 0


def test_pure_mode_no_provider_uses_fallback_only(monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings().model_copy(update={"nexa_pure_local_llm_mode": True, "use_real_llm": True})
    monkeypatch.setattr("app.services.intent_classifier.get_settings", lambda: s)
    monkeypatch.setattr("app.services.llm.completion.providers_available", lambda: False)

    called: dict[str, int] = {"n": 0}

    def _fake_llm(*_a, **_kw):
        called["n"] += 1
        return {"intent": "greeting", "confidence": 1.0, "reason": "x"}

    monkeypatch.setattr("app.services.intent_classifier.classify_intent_llm", _fake_llm)
    out = get_intent("buy milk, call dentist")
    assert out == "brain_dump"
    assert called["n"] == 0


def test_pure_mode_composer_offline_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    s = get_settings().model_copy(update={"nexa_pure_local_llm_mode": True, "use_real_llm": True})
    monkeypatch.setattr("app.services.response_composer.get_settings", lambda: s)
    monkeypatch.setattr("app.services.response_composer.providers_available", lambda: False)
    monkeypatch.setattr("app.services.response_composer.use_real_llm", lambda: False)

    ctx = ResponseContext(
        user_message="hello",
        intent="greeting",
        behavior="assist",
        has_active_plan=False,
        focus_task=None,
        selected_tasks=[],
        deferred_lines=[],
        planning_style="gentle",
        detected_state=None,
    )

    res = compose_response(ctx)
    assert "Ollama" in res["message"] or "reachable" in res["message"].lower()
