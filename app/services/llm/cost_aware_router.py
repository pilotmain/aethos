"""
Phase 70 — opt-in cost-aware model selection helper.

This module is a *thin* layer on top of the existing
:mod:`app.services.llm_costs` pricing table and
:mod:`app.services.llm.registry` provider registry. It deliberately does **not**
replace the LLM gateway / provider routing — it only provides:

* :func:`select_model_for_task` — pick a (provider, model) pair for a task type
  based on the cost-aware settings (default tier vs. cheap tier).
* :func:`estimate_messages_cost` — wrap
  :func:`app.services.llm_costs.estimate_llm_cost` with a quick token-count
  heuristic suitable for budget gates.
* :func:`recommend_cheaper_model_if_over_budget` — when the estimated cost
  exceeds the configured per-task budget, return the cheap-tier
  ``(provider, model)`` so the caller may swap before sending the request.
* :func:`route_for_task` — convenience wrapper that returns the chosen
  ``(provider, model, estimated_cost_usd, used_cheaper)`` tuple in one call.

Every function is a no-op unless ``Settings.nexa_cost_aware_enabled`` is True.
Existing call sites are not modified — integrations land per call site (start
with sub-agent execution and intent classification when those flows opt in).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from app.core.config import Settings, get_settings
from app.services.llm_costs import estimate_llm_cost

logger = logging.getLogger(__name__)


# Coarse mapping from agent / task domains to the tier we want by default.
# "cheap" → cheap-tier model (e.g., haiku / mini), "default" → premium model.
# Entries default to "default" when missing — opt cheap explicitly.
TASK_TIER_HINTS: dict[str, str] = {
    # Cheap-tier domains (routine, structured, low-stakes).
    "intent": "cheap",
    "intent_classification": "cheap",
    "summarization": "cheap",
    "summarize": "cheap",
    "chat": "cheap",
    "general_chat": "cheap",
    "qa": "cheap",
    "security_scan": "cheap",
    "linting": "cheap",
    # Default-tier domains (multi-step, planning, code generation).
    "planning": "default",
    "plan": "default",
    "agent": "default",
    "orchestration": "default",
    "execution": "default",
    "code_generation": "default",
    "analysis": "default",
}


@dataclass(frozen=True)
class CostAwareDecision:
    """Result of :func:`route_for_task` — fully describes the routing choice."""

    provider: str
    model: str
    tier: str  # "default" | "cheap"
    estimated_cost_usd: float | None
    over_budget: bool
    used_cheaper: bool
    enabled: bool


def _settings(settings: Settings | None) -> Settings:
    return settings or get_settings()


def _normalize_messages(messages: Iterable[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in messages or []:
        if isinstance(msg, dict):
            out.append(msg)
        else:
            out.append({"role": "user", "content": str(msg)})
    return out


def estimate_token_count(messages: Iterable[Any]) -> int:
    """
    Rough char/4 token heuristic so callers don't have to import tiktoken just to
    decide whether to swap models. Good enough for budget gates; use the provider
    SDK's own counter when you need exact accounting.
    """
    total_chars = 0
    for msg in _normalize_messages(messages):
        content = msg.get("content")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text") or part.get("content") or ""
                    if isinstance(text, str):
                        total_chars += len(text)
                else:
                    total_chars += len(str(part))
        else:
            total_chars += len(str(content or ""))
    return max(1, total_chars // 4)


def select_model_for_task(
    task_type: str | None,
    *,
    settings: Settings | None = None,
    force_tier: str | None = None,
) -> tuple[str, str, str]:
    """
    Pick ``(provider, model, tier)`` for ``task_type`` using ``TASK_TIER_HINTS``.

    When cost-aware routing is disabled, always returns the configured default tier
    (callers can still call this for telemetry without behavior change). Pass
    ``force_tier="cheap"`` or ``force_tier="default"`` to override the heuristic.
    """
    s = _settings(settings)
    tier = (force_tier or "").strip().lower() or None
    if tier not in {"default", "cheap"}:
        if not bool(getattr(s, "nexa_cost_aware_enabled", False)):
            tier = "default"
        else:
            hint = TASK_TIER_HINTS.get((task_type or "").strip().lower(), "default")
            tier = hint if hint in {"default", "cheap"} else "default"

    if tier == "cheap":
        return (
            (getattr(s, "nexa_cost_aware_cheap_provider", "") or "").strip() or "anthropic",
            (getattr(s, "nexa_cost_aware_cheap_model", "") or "").strip() or "claude-haiku-4-5",
            "cheap",
        )
    return (
        (getattr(s, "nexa_cost_aware_default_provider", "") or "").strip() or "anthropic",
        (getattr(s, "nexa_cost_aware_default_model", "") or "").strip() or "claude-sonnet-4-5",
        "default",
    )


def estimate_messages_cost(
    provider: str,
    model: str,
    messages: Iterable[Any],
    *,
    expected_output_tokens: int = 512,
) -> float | None:
    """
    Wraps :func:`app.services.llm_costs.estimate_llm_cost` using the heuristic
    token counter. Returns ``None`` when the provider/model isn't in the pricing
    table (e.g., Ollama / Gemini), which the caller should treat as "unknown — do
    not gate". ``expected_output_tokens`` defaults to 512 — tune per call site.
    """
    input_tokens = estimate_token_count(messages)
    out_tokens = max(0, int(expected_output_tokens or 0))
    return estimate_llm_cost(provider, model, input_tokens, out_tokens)


def recommend_cheaper_model_if_over_budget(
    provider: str,
    model: str,
    estimated_cost_usd: float | None,
    *,
    settings: Settings | None = None,
) -> tuple[str, str] | None:
    """
    If ``estimated_cost_usd`` is above
    :data:`Settings.nexa_cost_aware_max_per_task_usd`, return the cheap-tier
    ``(provider, model)`` for the caller to swap to. Returns ``None`` when the
    cost is unknown, the budget is unset, or the call is already on the cheap
    tier (no further downgrade available).
    """
    s = _settings(settings)
    if not bool(getattr(s, "nexa_cost_aware_enabled", False)):
        return None
    if estimated_cost_usd is None:
        return None
    budget = float(getattr(s, "nexa_cost_aware_max_per_task_usd", 0.0) or 0.0)
    if budget <= 0:
        return None
    if estimated_cost_usd <= budget:
        return None

    cheap_provider = (getattr(s, "nexa_cost_aware_cheap_provider", "") or "").strip() or "anthropic"
    cheap_model = (getattr(s, "nexa_cost_aware_cheap_model", "") or "").strip() or "claude-haiku-4-5"
    if (provider or "").strip().lower() == cheap_provider.lower() and (
        (model or "").strip().lower() == cheap_model.lower()
    ):
        return None
    return cheap_provider, cheap_model


def route_for_task(
    task_type: str | None,
    messages: Iterable[Any],
    *,
    expected_output_tokens: int = 512,
    settings: Settings | None = None,
) -> CostAwareDecision:
    """
    One-shot decision: pick a default-tier model, estimate cost, downgrade to
    the cheap tier when over budget, and return the full :class:`CostAwareDecision`
    so the caller can log the choice. Caller is responsible for actually invoking
    the LLM via :mod:`app.services.llm.registry` (or whatever gateway they use).
    """
    s = _settings(settings)
    enabled = bool(getattr(s, "nexa_cost_aware_enabled", False))
    provider, model, tier = select_model_for_task(task_type, settings=s)
    estimated = estimate_messages_cost(
        provider, model, messages, expected_output_tokens=expected_output_tokens
    )
    used_cheaper = False
    over_budget = False

    if enabled and estimated is not None:
        budget = float(getattr(s, "nexa_cost_aware_max_per_task_usd", 0.0) or 0.0)
        over_budget = budget > 0 and estimated > budget
        downgrade = recommend_cheaper_model_if_over_budget(
            provider, model, estimated, settings=s
        )
        if downgrade is not None:
            provider, model = downgrade
            tier = "cheap"
            used_cheaper = True
            estimated = estimate_messages_cost(
                provider, model, messages, expected_output_tokens=expected_output_tokens
            )

    decision = CostAwareDecision(
        provider=provider,
        model=model,
        tier=tier,
        estimated_cost_usd=estimated,
        over_budget=over_budget,
        used_cheaper=used_cheaper,
        enabled=enabled,
    )
    logger.info(
        "cost_aware_router decision task=%s tier=%s provider=%s model=%s "
        "estimated_usd=%s over_budget=%s used_cheaper=%s enabled=%s",
        task_type,
        decision.tier,
        decision.provider,
        decision.model,
        f"{decision.estimated_cost_usd:.6f}" if decision.estimated_cost_usd is not None else None,
        decision.over_budget,
        decision.used_cheaper,
        decision.enabled,
    )
    return decision


__all__ = [
    "CostAwareDecision",
    "TASK_TIER_HINTS",
    "estimate_messages_cost",
    "estimate_token_count",
    "recommend_cheaper_model_if_over_budget",
    "route_for_task",
    "select_model_for_task",
]
