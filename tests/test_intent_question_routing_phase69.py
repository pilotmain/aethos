"""Phase 69 — interrogative messages must not be hijacked by the dev pipeline.

Verifies that ``looks_like_informational_question`` (and the ``get_intent`` fast-path
that uses it) routes question-shaped queries to ``general_chat`` /
``capability_question`` while leaving provider, pain, and imperative cases on the
existing ``stuck_dev`` / ``external_*`` / ``orchestrate_system`` paths.
"""

from __future__ import annotations

import pytest

from app.services import intent_classifier
from app.services.intent_classifier import (
    classify_intent_fallback,
    get_intent,
    looks_like_informational_question,
)


def _fail_llm(*_a, **_k):
    raise AssertionError("LLM intent classifier must not be invoked for informational questions")


@pytest.mark.parametrize(
    "message",
    [
        "what do you need to deploy to AWS?",
        "How would I deploy an app?",
        "Can you explain AWS deployment?",
        "Tell me about deploying to the cloud",
        "I'm curious about AWS",
        "Why does Kubernetes ingress exist?",
        "What is GitOps?",
    ],
)
def test_informational_question_routes_to_general_chat_without_llm(monkeypatch, message: str) -> None:
    monkeypatch.setattr(intent_classifier, "classify_intent_llm", _fail_llm)
    assert looks_like_informational_question(message) is True
    assert get_intent(message) == "general_chat"


def test_capability_question_still_wins_over_general_chat(monkeypatch) -> None:
    monkeypatch.setattr(intent_classifier, "classify_intent_llm", _fail_llm)
    assert get_intent("Can you do design work for me?") == "capability_question"
    assert get_intent("what can you do?") == "capability_question"


@pytest.mark.parametrize(
    "message",
    [
        "deploy now",
        "push to production",
        "deploy my app to AWS now",
        "let's deploy to staging",
        "run the deployment please",
        "ship it",
    ],
)
def test_action_commands_are_not_treated_as_informational(message: str) -> None:
    assert looks_like_informational_question(message) is False


@pytest.mark.parametrize(
    "message",
    [
        "Why is my Railway service unhealthy",
        "How do I fix this Vercel build that keeps failing?",
        "what's broken on Heroku right now?",
    ],
)
def test_provider_and_pain_questions_stay_on_existing_paths(message: str) -> None:
    assert looks_like_informational_question(message) is False


def test_existing_stuck_dev_classification_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(
        intent_classifier,
        "classify_intent_llm",
        lambda msg, conversation_snapshot=None, **_: {
            "intent": "stuck",
            "confidence": 0.95,
            "reason": "mock",
        },
    )
    assert get_intent("kubernetes ingress returns 502 every time — ERROR") == "stuck_dev"


def test_existing_external_investigation_intent_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(intent_classifier, "classify_intent_llm", _fail_llm)
    assert get_intent("Why is my Railway service unhealthy") == "external_investigation"


def test_existing_external_execution_intent_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(intent_classifier, "classify_intent_llm", _fail_llm)
    assert (
        get_intent("Can you check Railway, fix repo, push, redeploy, and report?")
        == "external_execution"
    )


def test_url_in_question_defers_to_normal_routing() -> None:
    assert (
        looks_like_informational_question(
            "what about https://my-app.up.railway.app — is that wrong?"
        )
        is False
    )


def test_settings_flag_disables_short_circuit(monkeypatch) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "nexa_informational_question_skip_llm", False)

    captured: dict[str, str] = {}

    def fake_llm(msg, conversation_snapshot=None, **_):
        captured["msg"] = msg
        return {"intent": "general_chat", "confidence": 0.5, "reason": "mock"}

    monkeypatch.setattr(intent_classifier, "classify_intent_llm", fake_llm)

    assert get_intent("what is GitOps?") == "general_chat"
    assert captured.get("msg") == "what is GitOps?"


def test_fallback_classifier_unaffected_by_flag() -> None:
    """``classify_intent_fallback`` keeps its original behavior — short-circuit lives in ``get_intent``."""
    r = classify_intent_fallback("how do I deploy?")
    assert r["intent"] in {"general_chat", "capability_question"}
