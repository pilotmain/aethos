"""Tests for NEXA_LLM_INTELLIGENCE_LEVEL presets."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.host_executor_intent import parse_intelligence_query_intent
from app.services.llm_intelligence import (
    build_intelligence_public_dict,
    normalize_intelligence_level,
    resolve_effective_anthropic_model_id,
)


def test_normalize_intelligence_level() -> None:
    assert normalize_intelligence_level("ECONOMY") == "economy"
    assert normalize_intelligence_level("bogus") == "balanced"


def test_resolve_effective_anthropic_model_id_tier_on() -> None:
    s = MagicMock(
        nexa_llm_intelligence_apply_to_anthropic=True,
        nexa_llm_intelligence_level="economy",
        anthropic_model="claude-haiku-4-5-20251001",
    )
    assert "haiku" in resolve_effective_anthropic_model_id(s).lower()
    s.nexa_llm_intelligence_level = "balanced"
    assert resolve_effective_anthropic_model_id(s) == "claude-sonnet-4-5"
    s.nexa_llm_intelligence_level = "premium"
    assert "opus" in resolve_effective_anthropic_model_id(s).lower()


def test_resolve_respects_explicit_tier_off() -> None:
    s = MagicMock(
        nexa_llm_intelligence_apply_to_anthropic=False,
        nexa_llm_intelligence_level="economy",
        anthropic_model="custom-model-id",
    )
    assert resolve_effective_anthropic_model_id(s) == "custom-model-id"


def test_build_intelligence_public_dict_keys() -> None:
    s = MagicMock(
        nexa_llm_intelligence_apply_to_anthropic=True,
        nexa_llm_intelligence_level="balanced",
        anthropic_model="claude-haiku-4-5-20251001",
    )
    d = build_intelligence_public_dict(s)
    assert d["level"] == "balanced"
    assert d["model"] == "claude-sonnet-4-5"
    assert "cost_hint_usd_per_1m_tokens" in d


def test_parse_intelligence_query_intent() -> None:
    assert parse_intelligence_query_intent("what intelligence level am I using") is not None
    assert parse_intelligence_query_intent("deploy") is None


@pytest.mark.parametrize(
    "msg",
    [
        "what model tier is active",
        "show llm settings",
        "how smart are you",
    ],
)
def test_parse_intelligence_query_variants(msg: str) -> None:
    assert parse_intelligence_query_intent(msg) is not None
