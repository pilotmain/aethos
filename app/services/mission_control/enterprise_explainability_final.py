# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise explainability completion (Phase 4 Step 14)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_explainability_center import build_runtime_explainability_center
from app.services.mission_control.runtime_routing_visibility import build_routing_explanations


def build_enterprise_explainability_final(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    center = build_runtime_explainability_center(truth)
    routing = build_routing_explanations(truth)
    fallback = bool((truth.get("routing_summary") or {}).get("fallback_used"))
    degradation = (truth.get("runtime_resilience") or {}).get("status") not in (None, "healthy")
    return {
        "enterprise_explainability_final": {
            "why_routing": _first_reason(center, "routing") or "Advisory routing under orchestrator authority.",
            "why_fallback": "AethOS temporarily used an alternate provider — see routing explanations."
            if fallback
            else "No provider fallback — primary route in use.",
            "why_degradation": "Runtime resilience reduced — recovery center explains continuity."
            if degradation
            else "Runtime healthy — full operational visibility.",
            "why_recovery": center.get("recovery_explanation"),
            "why_advisories": "Strategic advisories are operator-approved recommendations only.",
            "why_recommendations": "Recommendations derive from bounded operational intelligence.",
            "orchestrator_doing": "Coordinating workers, governing operations, routing providers.",
            "workers_doing": "Executing bounded specialist tasks under orchestrator supervision.",
            "providers_doing": "Serving as interchangeable reasoning engines — not autonomous owners.",
            "no_logs_required": True,
            "bounded": True,
        },
        "runtime_explainability_center": center,
        "routing_explanations": routing,
    }


def _first_reason(center: dict[str, Any], topic: str) -> str | None:
    for item in center.get("runtime_decision_explanations") or []:
        if isinstance(item, dict) and item.get("topic") == topic:
            return str(item.get("reason") or "")[:200] or None
    return None
