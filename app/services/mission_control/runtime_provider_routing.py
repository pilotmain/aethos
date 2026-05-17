# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Adaptive provider routing visibility (Phase 4 Step 10)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.intelligent_routing import build_intelligent_routing


DEFAULT_CHAINS: dict[str, list[str]] = {
    "quality": ["opus", "sonnet", "gpt-4", "gpt-4-mini"],
    "local_first": ["ollama", "sonnet", "gpt-4-mini"],
    "cost": ["gpt-4-mini", "sonnet", "ollama"],
}


def build_provider_fallback_chains(truth: dict[str, Any] | None = None) -> dict[str, list[str]]:
    truth = truth or {}
    pref = str(truth.get("AETHOS_ROUTING_PREFERENCE") or "balanced")
    if "local" in pref:
        return {"primary": DEFAULT_CHAINS["local_first"]}
    if "cost" in pref:
        return {"primary": DEFAULT_CHAINS["cost"]}
    return {"primary": DEFAULT_CHAINS["quality"]}


def build_routing_decision_explanations(truth: dict[str, Any] | None = None) -> list[dict[str, str]]:
    truth = truth or {}
    routing = truth.get("routing_summary") or {}
    explanations: list[dict[str, str]] = []
    if routing.get("fallback_used"):
        from app.services.mission_control.provider_routing_ux import format_calm_fallback_message

        prov = routing.get("fallback_provider") or routing.get("selected_provider") or "an alternate provider"
        explanations.append(
            {
                "decision": "fallback",
                "reason": format_calm_fallback_message(
                    provider=str(prov),
                    reason=routing.get("reason"),
                ),
            }
        )
    mode = truth.get("AETHOS_ROUTING_MODE") or "hybrid"
    explanations.append(
        {
            "decision": "mode",
            "reason": f"Routing mode {mode} — orchestrator advisory-first; operator approval for paid fallback.",
        }
    )
    if truth.get("AETHOS_LOCAL_FIRST") in ("true", True):
        explanations.append({"decision": "local_first", "reason": "Local-first preference active (Ollama when healthy)."})
    return explanations[:8]


def build_provider_fallback_history(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    st = load_runtime_state()
    return list(st.get("routing_failover_history") or [])[-12:]


def build_routing_effectiveness_scores(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    ir = build_intelligent_routing(truth)
    eff = ir.get("routing_effectiveness") or {}
    hist = build_provider_fallback_history(truth)
    return {
        **eff,
        "recent_failovers": len(hist),
        "advisory_first": ir.get("advisory_first", True),
    }


def build_runtime_provider_routing(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    intelligent = build_intelligent_routing(truth)
    return {
        "adaptive_provider_routing": {
            "provider_fallback_chains": build_provider_fallback_chains(truth),
            "capability_aware": True,
            "privacy_aware": truth.get("AETHOS_LOCAL_FIRST") in ("true", True),
            "cost_aware": str(truth.get("AETHOS_ROUTING_PREFERENCE") or "").find("cost") >= 0,
            "latency_aware": True,
            "local_first": intelligent.get("adaptive_provider_selection", {}).get("local_first"),
            "orchestrator_controlled": True,
            "advisory_visible": True,
        },
        "routing_decision_explanations": build_routing_decision_explanations(truth),
        "provider_fallback_history": build_provider_fallback_history(truth),
        "routing_effectiveness_scores": build_routing_effectiveness_scores(truth),
        "intelligent_routing": intelligent,
    }
