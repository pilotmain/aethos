# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Provider routing visibility — history, explanations, health matrix (Phase 4 Step 12)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_provider_routing import (
    build_provider_fallback_history,
    build_routing_decision_explanations,
    build_runtime_provider_routing,
)


def build_routing_history(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    hist = build_provider_fallback_history(truth)
    return {
        "events": hist,
        "count": len(hist),
        "unstable_providers": list({h.get("provider") for h in hist if isinstance(h, dict) and h.get("provider")})[:8],
        "bounded": True,
    }


def build_routing_explanations(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    routing = build_runtime_provider_routing(truth)
    return {
        "current": {
            "selected_provider": (truth or {}).get("routing_summary", {}).get("primary_provider"),
            "fallback_chain": routing.get("adaptive_provider_routing", {}).get("provider_fallback_chains"),
            "routing_reason": (routing.get("intelligent_routing") or {}).get("routing_reason"),
            "privacy_impact": "local-first" if routing.get("adaptive_provider_routing", {}).get("privacy_aware") else "standard",
            "cost_impact": "cost-aware" if routing.get("adaptive_provider_routing", {}).get("cost_aware") else "balanced",
            "degraded_fallback": (truth or {}).get("routing_summary", {}).get("fallback_used"),
        },
        "explanations": build_routing_decision_explanations(truth),
        "advisory_first": True,
    }


def build_provider_health_matrix(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    providers = truth.get("providers") or {}
    rows: list[dict[str, Any]] = []
    if isinstance(providers, dict):
        for name, meta in list(providers.items())[:12]:
            if isinstance(meta, dict):
                rows.append(
                    {
                        "provider": name,
                        "status": meta.get("status") or "unknown",
                        "recent_actions": len(meta.get("recent_actions") or []),
                    }
                )
    routing = truth.get("routing_summary") or {}
    if routing.get("primary_provider") and not any(r.get("provider") == routing.get("primary_provider") for r in rows):
        rows.insert(0, {"provider": routing.get("primary_provider"), "status": "primary", "recent_actions": 0})
    return {"providers": rows, "matrix_health": "nominal" if rows else "unknown", "bounded": True}
