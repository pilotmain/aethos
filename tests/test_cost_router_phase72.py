"""
Phase 72 — production wiring tests for the cost-aware router.

Phase 70 introduced :mod:`app.services.llm.cost_aware_router` with tier-based
selection (``default`` vs. ``cheap``). Phase 72 layers on:

* ``parse_domain_model_overrides`` — reads
  :data:`Settings.nexa_cost_aware_default_model_per_domain` (a JSON map).
* ``select_model_for_task`` — honors the domain map BEFORE tier hints when
  cost-aware routing is enabled.
* ``route_for_task`` — surfaces ``domain_override=True`` and skips the
  over-budget downgrade for explicit operator choices.

Pricing comes from the existing :mod:`app.services.llm_costs` table; we don't
mock it.
"""

from __future__ import annotations

import json

import pytest

from app.services.llm.cost_aware_router import (
    parse_domain_model_overrides,
    route_for_task,
    select_model_for_task,
)


class _SettingsBase:
    nexa_cost_aware_enabled = True
    nexa_cost_aware_max_per_task_usd = 0.05
    nexa_cost_aware_default_provider = "anthropic"
    nexa_cost_aware_default_model = "claude-sonnet-4-5"
    nexa_cost_aware_cheap_provider = "anthropic"
    nexa_cost_aware_cheap_model = "claude-haiku-4-5"
    nexa_cost_aware_default_model_per_domain = ""


@pytest.fixture()
def settings(monkeypatch) -> _SettingsBase:
    s = _SettingsBase()
    monkeypatch.setattr(
        "app.services.llm.cost_aware_router.get_settings",
        lambda: s,
    )
    return s


def test_domain_map_empty_when_unset(settings: _SettingsBase) -> None:
    settings.nexa_cost_aware_default_model_per_domain = ""
    assert parse_domain_model_overrides() == {}


def test_domain_map_invalid_json_logs_and_returns_empty(settings: _SettingsBase) -> None:
    settings.nexa_cost_aware_default_model_per_domain = "{not_json"
    assert parse_domain_model_overrides() == {}


def test_domain_map_non_object_returns_empty(settings: _SettingsBase) -> None:
    settings.nexa_cost_aware_default_model_per_domain = json.dumps(["nope"])
    assert parse_domain_model_overrides() == {}


def test_domain_map_string_values_infer_provider(settings: _SettingsBase) -> None:
    settings.nexa_cost_aware_default_model_per_domain = json.dumps(
        {
            "qa": "claude-haiku-4-5",
            "ops": "gpt-4o-mini",
            "ml": "deepseek-chat",
            "scrum": "ollama/llama3.2",
        }
    )
    overrides = parse_domain_model_overrides()
    assert overrides["qa"] == ("anthropic", "claude-haiku-4-5")
    assert overrides["ops"] == ("openai", "gpt-4o-mini")
    assert overrides["ml"] == ("deepseek", "deepseek-chat")
    assert overrides["scrum"] == ("ollama", "llama3.2")


def test_domain_map_explicit_provider_prefix(settings: _SettingsBase) -> None:
    settings.nexa_cost_aware_default_model_per_domain = json.dumps(
        {"security": "anthropic/claude-sonnet-4-5"}
    )
    overrides = parse_domain_model_overrides()
    assert overrides["security"] == ("anthropic", "claude-sonnet-4-5")


def test_domain_map_dict_values(settings: _SettingsBase) -> None:
    settings.nexa_cost_aware_default_model_per_domain = json.dumps(
        {"design": {"provider": "openai", "model": "gpt-4o"}}
    )
    overrides = parse_domain_model_overrides()
    assert overrides["design"] == ("openai", "gpt-4o")


def test_domain_map_skips_invalid_entries(settings: _SettingsBase) -> None:
    settings.nexa_cost_aware_default_model_per_domain = json.dumps(
        {"qa": "", "ops": None, "valid": "claude-haiku-4-5"}
    )
    overrides = parse_domain_model_overrides()
    assert "qa" not in overrides
    assert "ops" not in overrides
    assert overrides["valid"] == ("anthropic", "claude-haiku-4-5")


def test_select_model_honors_domain_override_when_enabled(settings: _SettingsBase) -> None:
    settings.nexa_cost_aware_default_model_per_domain = json.dumps(
        {"qa": "claude-haiku-4-5", "ops": "gpt-4o-mini"}
    )
    provider, model, tier = select_model_for_task("ops")
    assert tier == "domain_override"
    assert provider == "openai"
    assert model == "gpt-4o-mini"


def test_select_model_domain_override_takes_precedence_over_tier_hint(
    settings: _SettingsBase,
) -> None:
    settings.nexa_cost_aware_default_model_per_domain = json.dumps(
        {"intent": "openai/gpt-4o-mini"}
    )
    provider, model, tier = select_model_for_task("intent")
    assert tier == "domain_override"
    assert (provider, model) == ("openai", "gpt-4o-mini")


def test_select_model_force_tier_overrides_domain_map(settings: _SettingsBase) -> None:
    settings.nexa_cost_aware_default_model_per_domain = json.dumps(
        {"qa": "claude-haiku-4-5"}
    )
    provider, model, tier = select_model_for_task("qa", force_tier="default")
    assert tier == "default"
    assert provider == settings.nexa_cost_aware_default_provider
    assert model == settings.nexa_cost_aware_default_model


def test_select_model_domain_map_ignored_when_disabled(monkeypatch) -> None:
    class Off:
        nexa_cost_aware_enabled = False
        nexa_cost_aware_default_provider = "anthropic"
        nexa_cost_aware_default_model = "claude-sonnet-4-5"
        nexa_cost_aware_cheap_provider = "anthropic"
        nexa_cost_aware_cheap_model = "claude-haiku-4-5"
        nexa_cost_aware_default_model_per_domain = json.dumps({"qa": "gpt-4o-mini"})

    monkeypatch.setattr(
        "app.services.llm.cost_aware_router.get_settings",
        lambda: Off(),
    )
    provider, model, tier = select_model_for_task("qa")
    assert tier == "default"
    assert (provider, model) == ("anthropic", "claude-sonnet-4-5")


def test_route_for_task_marks_domain_override(settings: _SettingsBase) -> None:
    settings.nexa_cost_aware_default_model_per_domain = json.dumps(
        {"ops": "gpt-4o-mini"}
    )
    decision = route_for_task("ops", [{"role": "user", "content": "hi"}])
    assert decision.tier == "domain_override"
    assert decision.domain_override is True
    assert decision.task_type == "ops"
    assert decision.provider == "openai"
    assert decision.model == "gpt-4o-mini"


def test_route_for_task_skips_downgrade_for_domain_override(settings: _SettingsBase) -> None:
    """
    A domain override is an explicit operator choice — even if the estimated cost
    blows the per-task budget, the router should not silently swap models.
    The decision still surfaces ``over_budget=True`` so the UI can warn.
    """
    settings.nexa_cost_aware_default_model_per_domain = json.dumps(
        {"big_task": "claude-sonnet-4-5"}  # premium model
    )
    settings.nexa_cost_aware_max_per_task_usd = 0.000001
    decision = route_for_task(
        "big_task",
        [{"role": "user", "content": "x" * 10_000}],
        expected_output_tokens=2000,
    )
    assert decision.domain_override is True
    assert decision.used_cheaper is False
    assert decision.model == "claude-sonnet-4-5"
    if decision.estimated_cost_usd is not None:
        assert decision.over_budget is True


def test_route_for_task_still_downgrades_heuristic_tier_over_budget(
    settings: _SettingsBase,
) -> None:
    settings.nexa_cost_aware_default_model_per_domain = ""  # no overrides
    settings.nexa_cost_aware_max_per_task_usd = 0.000001
    decision = route_for_task(
        "planning",
        [{"role": "user", "content": "x" * 10_000}],
        expected_output_tokens=2000,
    )
    assert decision.domain_override is False
    if decision.estimated_cost_usd is not None and decision.over_budget:
        assert decision.used_cheaper is True
        assert decision.tier == "cheap"
        assert decision.model == settings.nexa_cost_aware_cheap_model
