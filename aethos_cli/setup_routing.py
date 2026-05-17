# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Model routing preferences for setup (Phase 4 Step 4)."""

from __future__ import annotations

CANONICAL_ROUTING_MODES = {
    "local_only": {
        "label": "Local-first",
        "summary": "Local-first — Ollama and private models preferred on your machine.",
        "tradeoff": "Best privacy; requires local runtime health.",
    },
    "cloud_only": {
        "label": "Cloud-first",
        "summary": "Cloud-first — API providers when keys are configured.",
        "tradeoff": "Highest capability; uses external providers.",
    },
    "hybrid": {
        "label": "Hybrid",
        "summary": "Hybrid — local when healthy, calm cloud fallback when needed.",
        "tradeoff": "Balanced privacy and capability (recommended).",
    },
    "later": {
        "label": "Manual routing",
        "summary": "Manual routing — configure strategy after operational bootstrap.",
        "tradeoff": "Fastest setup; routing deferred.",
    },
}


def canonical_routing_label(mode: str) -> str:
    return CANONICAL_ROUTING_MODES.get(mode, {}).get("label") or "Hybrid"


def canonical_routing_summary(mode: str, preference: str = "balanced") -> str:
    base = CANONICAL_ROUTING_MODES.get(mode, CANONICAL_ROUTING_MODES["hybrid"])["summary"]
    if preference and preference != "balanced":
        return f"{base} Preference: {preference.replace('_', ' ')}."
    return base


def routing_summary(mode: str, preference: str) -> str:
    return canonical_routing_summary(mode, preference)


def build_routing_env_updates(
    mode: str,
    *,
    preference: str = "balanced",
    require_paid_fallback_approval: bool = True,
) -> dict[str, str]:
    """
    Map setup intelligence mode to env keys.

    mode: local_only | cloud_only | hybrid | later
    preference: best_quality | lowest_cost | local_first | balanced
    """
    updates: dict[str, str] = {
        "AETHOS_ROUTING_MODE": mode,
        "AETHOS_ROUTING_PREFERENCE": preference,
        "AETHOS_ROUTING_REQUIRE_PAID_APPROVAL": "true" if require_paid_fallback_approval else "false",
    }
    if mode == "local_only":
        updates["NEXA_LLM_PROVIDER"] = "ollama"
        updates["NEXA_OLLAMA_ENABLED"] = "true"
        updates["AETHOS_LOCAL_FIRST"] = "true"
        updates["AETHOS_LOCAL_ONLY"] = "true"
    elif mode == "cloud_only":
        updates["AETHOS_LOCAL_ONLY"] = "false"
        updates["AETHOS_LOCAL_FIRST"] = "false"
    elif mode == "hybrid":
        updates["AETHOS_LOCAL_FIRST"] = "true"
        updates["AETHOS_LOCAL_ONLY"] = "false"
        updates["NEXA_OLLAMA_ENABLED"] = "true"
    else:
        updates["AETHOS_ROUTING_DEFERRED"] = "true"
    return updates
