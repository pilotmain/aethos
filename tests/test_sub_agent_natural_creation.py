"""Orchestration sub-agent natural-language routing (Phase 46)."""

from __future__ import annotations

from app.services.sub_agent_natural_creation import (
    normalize_sub_agent_domain,
    parse_natural_sub_agent_specs,
    prefers_registry_sub_agent,
)


def test_prefers_registry_vs_custom_product() -> None:
    assert prefers_registry_sub_agent("create agent qa_agent test") is True
    assert prefers_registry_sub_agent("create two agents qa_agent and marketing_agent") is True
    assert prefers_registry_sub_agent("create a custom agent called legal-reviewer") is False
    assert prefers_registry_sub_agent("create custom agent qa_agent for QA") is True


def test_numbered_custom_list_not_registry() -> None:
    body = "Create me a few agents:\n1. financial advisor\n2. fitness coach"
    assert prefers_registry_sub_agent(body) is False


def test_parse_cli_and_pairs() -> None:
    assert parse_natural_sub_agent_specs("subagent create ops_agent ops") == [("ops_agent", "ops")]
    assert parse_natural_sub_agent_specs("/subagent create foo git") == [("foo", "git")]
    assert parse_natural_sub_agent_specs("create agent security_expert security") == [
        ("security_expert", "security")
    ]


def test_parse_multi_and_handles() -> None:
    spec = parse_natural_sub_agent_specs("create two agents qa_agent and marketing_agent")
    assert len(spec) == 2
    assert spec[0][0] == "qa_agent"
    assert spec[1][0] == "marketing_agent"
    assert spec[0][1] == "qa"
    assert spec[1][1] == "marketing"


def test_normalize_security_and_qa() -> None:
    assert normalize_sub_agent_domain("security") == "security"
    assert normalize_sub_agent_domain("qa") == "qa"
    assert normalize_sub_agent_domain("quality") == "qa"
