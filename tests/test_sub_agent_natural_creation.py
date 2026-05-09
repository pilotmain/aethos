"""Orchestration sub-agent natural-language routing (Phase 46)."""

from __future__ import annotations

from app.services.sub_agent_natural_creation import (
    normalize_sub_agent_domain,
    parse_natural_sub_agent_specs,
    prefers_registry_sub_agent,
    _fallback_registry_specs_from_explicit_nl,
)


def test_prefers_registry_vs_custom_product() -> None:
    assert prefers_registry_sub_agent("create agent qa_agent test") is True
    assert prefers_registry_sub_agent("create two agents qa_agent and marketing_agent") is True
    assert prefers_registry_sub_agent("create a custom agent called legal-reviewer") is True
    assert prefers_registry_sub_agent("create custom agent qa_agent for QA") is True


def test_numbered_roster_prefers_registry() -> None:
    body = "Create me a few agents:\n1. financial advisor\n2. fitness coach"
    assert prefers_registry_sub_agent(body) is True


def test_parse_numbered_multi_agents() -> None:
    raw = "create five agents:\n\n1. product_manager\n2. designer\n3. backend\n"
    spec = parse_natural_sub_agent_specs(raw)
    assert len(spec) == 3
    assert spec[0][0] == "product_manager"


def test_parse_numbered_freeform_titles() -> None:
    raw = "Create me five agents:\n\n1. financial advisor\n2. fitness coach\n"
    spec = parse_natural_sub_agent_specs(raw)
    assert len(spec) == 2
    assert spec[0][0] == "financial_advisor"
    assert spec[1][0] == "fitness_coach"


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


def test_fallback_explicit_named_extracts_handle() -> None:
    specs = _fallback_registry_specs_from_explicit_nl(
        "Create me a custom agent called @legal-reviewer. It reviews contracts."
    )
    assert specs and specs[0][0] == "legal-reviewer"


def test_normalize_security_and_qa() -> None:
    assert normalize_sub_agent_domain("security") == "security"
    assert normalize_sub_agent_domain("qa") == "qa"
    assert normalize_sub_agent_domain("quality") == "qa"


def test_infer_domain_phase54_product_and_design() -> None:
    from app.services.sub_agent_natural_creation import _infer_domain

    assert _infer_domain("product_manager_agent", "product_manager_agent for product strategy") == "general"
    assert _infer_domain("designer_agent", "designer_agent for UI/UX design") == "design"
    assert _infer_domain("backend_agent", "backend_agent for API development") == "backend"


def test_conversational_create_agent_parsing() -> None:
    s = parse_natural_sub_agent_specs("Create a marketing agent")
    assert s and s[0][0] == "marketing_agent" and s[0][1] == "marketing"

    tail = parse_natural_sub_agent_specs("Create a marketing agent for product launch")
    assert tail and tail[0][0] == "marketing_agent" and tail[0][1] == "marketing"

    s2 = parse_natural_sub_agent_specs("Can you create a QA agent?")
    assert s2 and "qa" in s2[0][0].lower() and s2[0][1] == "qa"

    s3 = parse_natural_sub_agent_specs("I need a QA specialist")
    assert s3 and s3[0][1] == "qa"


def test_prefers_registry_conversational_spawn() -> None:
    from app.services.sub_agent_natural_creation import looks_like_registry_agent_creation_nl

    assert looks_like_registry_agent_creation_nl("Create a marketing agent") is True
    assert looks_like_registry_agent_creation_nl("Can you create a marketing agent?") is True
    assert looks_like_registry_agent_creation_nl("I need a QA specialist") is True
    assert looks_like_registry_agent_creation_nl("Set up a testing agent") is True
