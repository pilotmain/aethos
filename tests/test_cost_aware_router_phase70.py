# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 70 — :mod:`app.services.llm.cost_aware_router` unit tests.

The router is opt-in: when the settings flag is off, no behavior change should
escape from :func:`route_for_task`. Pricing comes from the existing
:mod:`app.services.llm_costs` table; we don't mock it.
"""

from __future__ import annotations

import pytest

from app.services.llm.cost_aware_router import (
    CostAwareDecision,
    estimate_messages_cost,
    estimate_token_count,
    recommend_cheaper_model_if_over_budget,
    route_for_task,
    select_model_for_task,
)


class _Settings:
    nexa_cost_aware_enabled = True
    nexa_cost_aware_max_per_task_usd = 0.05
    nexa_cost_aware_default_provider = "anthropic"
    nexa_cost_aware_default_model = "claude-sonnet-4-5"
    nexa_cost_aware_cheap_provider = "anthropic"
    nexa_cost_aware_cheap_model = "claude-haiku-4-5"


@pytest.fixture()
def cost_settings(monkeypatch) -> _Settings:
    s = _Settings()
    monkeypatch.setattr(
        "app.services.llm.cost_aware_router.get_settings",
        lambda: s,
    )
    return s


def test_estimate_token_count_handles_dict_and_string_messages() -> None:
    assert estimate_token_count([]) == 1
    assert estimate_token_count(["hello world"]) >= 1
    msgs = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "world"}]
    assert estimate_token_count(msgs) >= 2


def test_select_model_default_when_disabled(monkeypatch) -> None:
    class Off:
        nexa_cost_aware_enabled = False
        nexa_cost_aware_default_provider = "anthropic"
        nexa_cost_aware_default_model = "claude-sonnet-4-5"
        nexa_cost_aware_cheap_provider = "anthropic"
        nexa_cost_aware_cheap_model = "claude-haiku-4-5"

    monkeypatch.setattr("app.services.llm.cost_aware_router.get_settings", lambda: Off())
    provider, model, tier = select_model_for_task("intent")
    assert tier == "default"
    assert provider == "anthropic"
    assert model == "claude-sonnet-4-5"


def test_select_model_cheap_for_intent_when_enabled(cost_settings: _Settings) -> None:
    provider, model, tier = select_model_for_task("intent_classification")
    assert tier == "cheap"
    assert provider == cost_settings.nexa_cost_aware_cheap_provider
    assert model == cost_settings.nexa_cost_aware_cheap_model


def test_select_model_default_for_planning_when_enabled(cost_settings: _Settings) -> None:
    _provider, model, tier = select_model_for_task("planning")
    assert tier == "default"
    assert model == cost_settings.nexa_cost_aware_default_model


def test_recommend_cheaper_when_over_budget(cost_settings: _Settings) -> None:
    rec = recommend_cheaper_model_if_over_budget(
        "anthropic", "claude-sonnet-4-5", 0.10
    )
    assert rec is not None
    cheap_provider, cheap_model = rec
    assert cheap_provider == cost_settings.nexa_cost_aware_cheap_provider
    assert cheap_model == cost_settings.nexa_cost_aware_cheap_model


def test_recommend_skipped_when_under_budget(cost_settings: _Settings) -> None:
    assert recommend_cheaper_model_if_over_budget(
        "anthropic", "claude-sonnet-4-5", 0.001
    ) is None


def test_recommend_skipped_when_already_on_cheap_tier(cost_settings: _Settings) -> None:
    assert recommend_cheaper_model_if_over_budget(
        "anthropic", "claude-haiku-4-5", 5.0
    ) is None


def test_recommend_skipped_when_disabled(monkeypatch) -> None:
    class Off:
        nexa_cost_aware_enabled = False
        nexa_cost_aware_max_per_task_usd = 0.01
        nexa_cost_aware_cheap_provider = "anthropic"
        nexa_cost_aware_cheap_model = "claude-haiku-4-5"

    monkeypatch.setattr("app.services.llm.cost_aware_router.get_settings", lambda: Off())
    assert recommend_cheaper_model_if_over_budget(
        "anthropic", "claude-sonnet-4-5", 5.0
    ) is None


def test_estimate_messages_cost_returns_none_for_unknown_provider(cost_settings: _Settings) -> None:
    assert (
        estimate_messages_cost("ollama", "llama3.2", [{"role": "user", "content": "hi"}])
        is None
    )


def test_route_for_task_downgrades_when_over_budget(monkeypatch) -> None:
    class Tight(_Settings):
        nexa_cost_aware_max_per_task_usd = 0.000001

    monkeypatch.setattr(
        "app.services.llm.cost_aware_router.get_settings", lambda: Tight()
    )
    huge = "x" * 200_000
    decision = route_for_task("planning", [{"role": "user", "content": huge}])
    assert isinstance(decision, CostAwareDecision)
    assert decision.enabled is True
    assert decision.used_cheaper is True
    assert decision.tier == "cheap"
    assert decision.estimated_cost_usd is not None


def test_route_for_task_no_downgrade_when_disabled(monkeypatch) -> None:
    class Off:
        nexa_cost_aware_enabled = False
        nexa_cost_aware_max_per_task_usd = 0.000001
        nexa_cost_aware_default_provider = "anthropic"
        nexa_cost_aware_default_model = "claude-sonnet-4-5"
        nexa_cost_aware_cheap_provider = "anthropic"
        nexa_cost_aware_cheap_model = "claude-haiku-4-5"

    monkeypatch.setattr("app.services.llm.cost_aware_router.get_settings", lambda: Off())
    huge = "x" * 200_000
    decision = route_for_task("planning", [{"role": "user", "content": huge}])
    assert decision.enabled is False
    assert decision.used_cheaper is False
    assert decision.tier == "default"
    assert decision.model == "claude-sonnet-4-5"
