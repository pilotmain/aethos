# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Strategic differentiation beyond OpenClaw (Phase 4 Step 1)."""

from __future__ import annotations

from typing import Any

from app.services.aethos_differentiation import build_differentiators_summary


def build_strategic_differentiation_summary(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    base = build_differentiators_summary(ort=truth.get("_ort"))
    return {
        **base,
        "phase4_advantages": [
            "adaptive_operational_intelligence",
            "enterprise_operational_memory",
            "runtime_evolution_governance",
            "strategic_runtime_awareness",
            "operational_maturity_visibility",
            "mission_control_cohesion",
            "operational_calmness_lock",
            "incremental_truth_hydration",
        ],
        "openclaw_parity": "preserved",
        "differentiation_version": "phase4_step3",
        "step2_advantages": [
            "adaptive_coordination",
            "strategic_runtime_forecasting",
            "worker_ecosystem_coordination",
            "runtime_evolution_memory",
            "strategic_governance_progression",
        ],
        "step3_advantages": [
            "adaptive_runtime_optimization",
            "operational_intelligence_ecosystem",
            "governance_operational_intelligence",
            "ecosystem_operational_strategy",
            "enterprise_operational_maturity_intelligence",
        ],
    }


def build_enterprise_operational_intelligence_advantage(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    summary = build_strategic_differentiation_summary(truth)
    return {
        "advantages": summary.get("step3_advantages") or summary.get("step2_advantages"),
        "ecosystem_coordinated": bool((truth or {}).get("operational_intelligence_ecosystem")),
        "openclaw_parity": "preserved",
    }


def build_runtime_ecosystem_positioning(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "positioning": "coordinated enterprise operational intelligence ecosystem",
        "optimization_advisory": True,
        "ecosystem_aware": True,
    }


def build_operational_optimization_advantage(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "optimization_quality": (truth or {}).get("runtime_optimization_quality"),
        "efficiency_signals": len((truth or {}).get("operational_efficiency_signals") or []),
        "explainable": True,
    }


def build_enterprise_operational_advantage(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    summary = build_strategic_differentiation_summary(truth)
    return {
        "advantages": summary.get("step2_advantages") or summary.get("phase4_advantages"),
        "openclaw_parity": summary.get("openclaw_parity"),
        "calm_operations": True,
    }


def build_runtime_strategy_positioning(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "positioning": "strategically adaptive enterprise operational operating system",
        "forecasting_advisory": True,
        "coordination_advisory": True,
    }


def build_operational_intelligence_advantage(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "strategic_insights": len((truth or {}).get("strategic_runtime_insights") or []),
        "bounded_forecasts": bool((truth or {}).get("operational_forecasting")),
        "explainable": True,
    }


def build_enterprise_advantage_visibility(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    summary = build_strategic_differentiation_summary(truth)
    return {
        "advantages": summary.get("phase4_advantages") or summary.get("advantages"),
        "privacy_first": True,
        "local_first_orchestration": True,
        "enterprise_trust_visible": truth.get("operational_trust_score") is not None if truth else True,
    }


def build_operational_positioning(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "positioning": "intelligent enterprise operational operating system",
        "beyond_parity": True,
        "advisory_evolution": True,
        "orchestrator_central": (truth or {}).get("runtime_identity", {}).get("orchestrator_central", True),
    }
