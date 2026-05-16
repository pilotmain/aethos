# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Strategic runtime intelligence (Phase 4 Step 2)."""

from __future__ import annotations

from typing import Any


def build_strategic_runtime_insights(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    truth = truth or {}
    insights: list[dict[str, Any]] = []
    readiness = float(truth.get("runtime_readiness_score") or 0.75)
    if readiness < 0.7:
        insights.append({"area": "deployment_stability", "trend": "attention", "advisory": True})
    trust = float(truth.get("operational_trust_score") or 0.8)
    if trust < 0.75:
        insights.append({"area": "operational_resilience", "trend": "review", "advisory": True})
    scale = (truth.get("runtime_scalability_health") or {}).get("status")
    if scale and scale != "healthy":
        insights.append({"area": "runtime_scalability", "trend": "growth_pressure", "advisory": True})
    worker_rel = (truth.get("worker_accountability") or {}).get("reliability")
    if worker_rel is not None and float(worker_rel) < 0.7:
        insights.append({"area": "worker_specialization", "trend": "evolving", "advisory": True})
    gov = (truth.get("governance_readiness") or {}).get("score")
    if gov is not None:
        insights.append(
            {
                "area": "governance_maturity",
                "trend": "progressing" if float(gov) >= 0.8 else "maturing",
                "advisory": True,
            }
        )
    return insights[:8]


def build_operational_forecasts(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    pressure = (truth.get("operational_pressure") or {}).get("level", "low")
    return {
        "deployment_stability": "stable" if pressure != "high" else "elevated_risk",
        "provider_ecosystem": "stable",
        "governance_escalation": "low" if pressure != "high" else "medium",
        "horizon": "short_term",
        "advisory": True,
        "runtime_derived": True,
    }


def build_runtime_trajectory(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    traj = (truth or {}).get("operational_trajectory_summary") or {}
    return {
        "direction": traj.get("direction", "stable"),
        "readiness_score": traj.get("readiness_score") or truth.get("runtime_readiness_score"),
        "trust_score": traj.get("trust_score") or truth.get("operational_trust_score"),
        "summary": traj.get("summary"),
        "phase": "phase4_step2",
    }


def build_operational_maturity_projection(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    scores = (truth or {}).get("operational_maturity_scores") or {}
    composite = (truth.get("enterprise_operational_posture") or {}).get("composite", 0.75)
    return {
        "projected_posture": "strong" if float(composite) >= 0.82 else "maturing",
        "domains": scores,
        "advisory": True,
    }
