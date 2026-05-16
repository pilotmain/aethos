# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime strategy guidance for installer (Phase 4 Step 15)."""

from __future__ import annotations

from typing import Any

STRATEGIES = {
    "local-first": {
        "summary": "Ollama primary — cloud fallback optional",
        "privacy": "Strong local privacy; data stays on your machine when using Ollama",
        "routing": "AethOS routes to local models first, cloud when needed",
    },
    "cloud-first": {
        "summary": "Cloud APIs primary — local optional",
        "privacy": "Cloud reasoning; configure keys and egress policy explicitly",
        "routing": "OpenAI, Anthropic, DeepSeek, and future providers",
    },
    "hybrid": {
        "summary": "Intelligent routing with privacy-aware fallback",
        "privacy": "Balances local and cloud based on task and policy",
        "routing": "AethOS routes work to the best available reasoning engine",
    },
    "configure-later": {
        "summary": "Bootstrap operations first — providers deferred",
        "privacy": "Operational shell ready; connect brains when you choose",
        "routing": "Routing activates when providers are configured",
    },
}


def build_runtime_strategy_onboarding(selected: str | None = None) -> dict[str, Any]:
    key = (selected or "hybrid").replace("_", "-")
    if key not in STRATEGIES:
        key = "hybrid"
    return {
        "runtime_strategy_onboarding": {
            "selected": key,
            "strategies": STRATEGIES,
            "routing_explainer": "AethOS routes work to the best available reasoning engine — orchestrator retains authority.",
            "examples": ["local model", "OpenAI", "Anthropic", "DeepSeek", "future providers"],
            "change_later": "Update `.env` or Mission Control provider settings anytime",
            "bounded": True,
        }
    }


def build_provider_routing_explained() -> dict[str, Any]:
    return {
        "provider_routing_explained": {
            "headline": "Providers are interchangeable reasoning engines",
            "orchestrator": "AethOS chooses routes; workers execute; providers reason",
            "advisory_first": True,
            "fallback": "Automatic fallback when a provider is unavailable",
            "bounded": True,
        }
    }
