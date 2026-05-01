"""Multi-agent capability routing vs greedy custom-agent creation."""

from __future__ import annotations

import pytest

from app.services.custom_agent_intent import is_custom_agent_creation_intent
from app.services.custom_agent_parser import is_valid_user_agent_handle, parse_custom_agent_from_prompt
from app.services.custom_agent_routing import is_create_custom_agent_request
from app.services.intent_classifier import classify_intent_fallback, get_intent
from app.services.multi_agent_routing import (
    is_multi_agent_capability_question,
    reply_multi_agent_capability_clarification,
)


MULTI_Q = (
    "can you create multi agents that can communicate each other autonomously "
    "and do some task without my involvement?"
)


def test_multi_agent_capability_question_detected() -> None:
    assert is_multi_agent_capability_question(MULTI_Q) is True
    clar = reply_multi_agent_capability_clarification().lower()
    assert "nexa" in clar and "dynamically" in clar


def test_explicit_team_for_goal_not_capability_question() -> None:
    assert (
        is_multi_agent_capability_question("create a multi-agent dev team for building a dashboard") is False
    )


def test_create_custom_agent_request_strict() -> None:
    assert is_create_custom_agent_request(
        "Create me a custom agent called @legal-reviewer. It reviews contracts."
    )
    assert not is_create_custom_agent_request(MULTI_Q)
    assert not is_create_custom_agent_request("can you create agents for me?")


def test_custom_agent_creation_intent_not_greedy() -> None:
    assert is_custom_agent_creation_intent(MULTI_Q) is False
    assert is_custom_agent_creation_intent("create an agent for notes") is True


def test_sentence_handle_invalid() -> None:
    assert is_valid_user_agent_handle("legal-reviewer") is True
    assert is_valid_user_agent_handle("can-you-create-multi-agents-that-com") is False
    assert parse_custom_agent_from_prompt(
        "create agent can you create multi agents that communicate"
    ) is None


def test_intent_fallback_multi_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.intent_classifier.classify_intent_llm",
        lambda msg, conversation_snapshot=None: classify_intent_fallback(msg),
    )
    assert get_intent(MULTI_Q) == "capability_question"
