# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final operator-facing runtime explainability (Phase 4 Step 23)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.enterprise_explainability_final import build_enterprise_explainability_final


def build_runtime_explainability_finalization(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    base = build_enterprise_explainability_final(truth) if truth else {}
    routing = (truth.get("provider_routing_ux") or {}).get("explanations") or []
    recovery = (truth.get("runtime_recovery_history") or {}).get("events") or []
    domains = {
        "routing_decisions": bool(routing) or bool((truth.get("routing_summary") or {})),
        "provider_failovers": bool((truth.get("routing_summary") or {}).get("fallback_used")),
        "runtime_recovery": bool(recovery),
        "degraded_mode": (truth.get("runtime_operational_state") or {}).get("state") in ("degraded", "partially_degraded"),
        "hydration_delays": bool((truth.get("hydration_progress") or {}).get("partial")),
        "recommendations": bool(truth.get("strategic_recommendations")),
        "automation_advisories": bool(truth.get("strategic_runtime_alerts")),
        "runtime_throttling": bool((truth.get("operational_throttling") or {}).get("throttled")),
        "continuity_recovery": bool((truth.get("runtime_continuity_certification") or {}).get("certified")),
    }
    return {
        "runtime_explainability_finalization": {
            **(base.get("enterprise_explainability") or {}),
            "domains_covered": domains,
            "operator_always_has_answer": all(domains.values()) or bool(routing),
            "phase": "phase4_step23",
            "bounded": True,
        }
    }
