from __future__ import annotations

from app.services.custom_agent_creation import (
    is_create_custom_agent_intent,
    parse_creation_spec,
    try_create_custom_agent_primitive,
)
from app.services.intent_classifier import get_intent


def test_intent_rule_create_agent() -> None:
    assert get_intent("create an agent for legal") == "create_sub_agent"
    assert get_intent("Create agent @foo") == "create_sub_agent"
    assert get_intent("  create agent x") == "create_sub_agent"
    assert get_intent("create a custom agent called helper") == "create_sub_agent"


def test_intent_not_misclassified() -> None:
    assert get_intent("I need to create a plan") != "create_custom_agent"


def test_is_create_custom_agent_intent() -> None:
    assert is_create_custom_agent_intent("create agent legal-reviewer") is True
    assert is_create_custom_agent_intent("recreate agent") is False


def test_parse_creation_spec_with_sections() -> None:
    text = """create agent legal-reviewer

Capabilities:
- contract review
- risk summarization
- drafting questions

Guardrails:
- requires human approval before final decisions
"""
    spec = parse_creation_spec(text)
    assert spec is not None
    assert "legal" in spec.display_title.lower() or spec.display_title == "legal-reviewer"
    assert "contract review" in spec.capabilities
    assert "human approval" in spec.guardrails[0].lower()


def test_try_primitive_returns_none_without_title() -> None:
    class _Db:
        pass

    assert try_create_custom_agent_primitive(_Db(), "web_test", "create agent") is None
