"""Anthropic model presets from ``NEXA_LLM_INTELLIGENCE_LEVEL`` (cost vs capability)."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings

_VALID_LEVELS = frozenset({"economy", "balanced", "premium"})

# Pinned ids in the Claude 4.x family (verify on Anthropic pricing / models docs).
ANTHROPIC_MODEL_BY_LEVEL: dict[str, str] = {
    "economy": "claude-haiku-4-5-20251001",
    "balanced": "claude-sonnet-4-5",
    "premium": "claude-opus-4-1-20250805",
}

# Rough blended USD / 1M tokens (informative only; dashboards are source of truth).
TIER_COST_HINT_USD_PER_1M: dict[str, float] = {
    "economy": 1.0,
    "balanced": 9.0,
    "premium": 45.0,
}

TIER_NOTES: dict[str, str] = {
    "economy": "Fast Haiku-class model — best for high-volume, simple tasks.",
    "balanced": "Sonnet-class default — good reasoning for most workloads.",
    "premium": "Opus-class — strongest reasoning; highest cost.",
}


def normalize_intelligence_level(raw: str | None) -> str:
    s = (raw or "balanced").strip().lower()
    return s if s in _VALID_LEVELS else "balanced"


def resolve_effective_anthropic_model_id(settings: Settings | None = None) -> str:
    """
    Model id used for Anthropic **primary registry** completions when tier apply is on.

    When ``nexa_llm_intelligence_apply_to_anthropic`` is false, returns ``anthropic_model``
    (``ANTHROPIC_MODEL``) unchanged.
    """
    s = settings or get_settings()
    if not bool(getattr(s, "nexa_llm_intelligence_apply_to_anthropic", True)):
        return (s.anthropic_model or "").strip() or ANTHROPIC_MODEL_BY_LEVEL["economy"]
    level = normalize_intelligence_level(getattr(s, "nexa_llm_intelligence_level", None))
    return ANTHROPIC_MODEL_BY_LEVEL[level]


def build_intelligence_public_dict(settings: Settings | None = None) -> dict[str, Any]:
    """Structured summary for gateway / CLI (no secrets)."""
    s = settings or get_settings()
    level = normalize_intelligence_level(getattr(s, "nexa_llm_intelligence_level", None))
    model = resolve_effective_anthropic_model_id(s)
    apply_tier = bool(getattr(s, "nexa_llm_intelligence_apply_to_anthropic", True))
    return {
        "level": level,
        "model": model,
        "cost_hint_usd_per_1m_tokens": float(TIER_COST_HINT_USD_PER_1M[level]),
        "intelligence_tier_applies": apply_tier,
        "anthropic_model_env": (s.anthropic_model or "").strip(),
        "tier_note": TIER_NOTES[level],
    }


def format_intelligence_gateway_markdown(info: dict[str, Any]) -> str:
    """Human-readable block for chat (markdown)."""
    apply = bool(info.get("intelligence_tier_applies"))
    env_m = str(info.get("anthropic_model_env") or "")
    lines = [
        "**LLM intelligence preset**",
        "",
        f"• **Level:** `{info.get('level')}`",
        f"• **Anthropic model in use:** `{info.get('model')}`",
        f"• **Rough cost hint:** ~${info.get('cost_hint_usd_per_1m_tokens'):.2f} / 1M tokens (blended estimate)",
        f"• **Note:** {info.get('tier_note')}",
        "",
    ]
    if apply:
        lines.append(
            "Tier mapping is **on** (`NEXA_LLM_INTELLIGENCE_APPLY_TO_ANTHROPIC=true`). "
            "Set it to `false` to force `ANTHROPIC_MODEL` only."
        )
    else:
        lines.append("Tier mapping is **off** — `ANTHROPIC_MODEL` controls the Anthropic provider.")
    if env_m and not apply:
        lines.append(f"• **ANTHROPIC_MODEL in env:** `{env_m}`")
    lines.extend(
        [
            "",
            "**Change in `.env` then restart API + bot:**",
            "`NEXA_LLM_INTELLIGENCE_LEVEL=economy|balanced|premium`",
            "",
            "- **economy** — cheapest preset (Haiku-class)",
            "- **balanced** — recommended default (Sonnet-class)",
            "- **premium** — strongest preset (Opus-class)",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "ANTHROPIC_MODEL_BY_LEVEL",
    "build_intelligence_public_dict",
    "format_intelligence_gateway_markdown",
    "normalize_intelligence_level",
    "resolve_effective_anthropic_model_id",
]
