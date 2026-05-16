# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise operational maturity and strategic outlook (Phase 4 Step 1)."""

from __future__ import annotations

from typing import Any


def build_operational_maturity_scores(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "runtime_maturity": float(truth.get("runtime_readiness_score") or 0.75),
        "governance_maturity": float((truth.get("governance_readiness") or {}).get("score") or 0.85),
        "scalability_maturity": float((truth.get("scalability_readiness") or {}).get("score") or 0.88),
        "trust_maturity": float(truth.get("operational_trust_score") or 0.8),
        "worker_ecosystem": float((truth.get("worker_accountability") or {}).get("reliability") or 0.8),
        "automation_ecosystem": float((truth.get("automation_trust") or {}).get("score") or 0.85),
    }


def build_enterprise_operational_posture(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    scores = build_operational_maturity_scores(truth)
    avg = sum(scores.values()) / max(1, len(scores))
    return {
        "overall_posture": "strong" if avg >= 0.8 else ("maturing" if avg >= 0.65 else "developing"),
        "scores": scores,
        "composite": round(avg, 3),
    }


def build_runtime_strategic_outlook(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    traj = (truth or {}).get("operational_trajectory_summary") or {}
    return {
        "outlook": traj.get("direction", "stable"),
        "summary": traj.get("summary"),
        "horizon": "short_term",
        "advisory": True,
    }


def build_operational_resilience_projection(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    hard = (truth or {}).get("production_hardening") or {}
    return {
        "resilient": hard.get("resilient", True),
        "projection": "stable" if hard.get("resilient") else "review_bounds",
    }


def build_runtime_resilience_maturity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    hard = (truth or {}).get("production_hardening") or {}
    return {
        "score": 0.9 if hard.get("resilient") else 0.65,
        "resilient": hard.get("resilient", True),
    }


def build_ecosystem_maturity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    worker = float((truth.get("worker_ecosystem_health") or {}).get("health_score") or 0.8)
    auto = float((truth.get("automation_operational_effectiveness") or {}).get("success_rate") or 0.85)
    return {
        "worker_ecosystem": round(worker, 3),
        "automation_ecosystem": round(auto, 3),
        "provider_ecosystem": 0.85,
        "composite": round((worker + auto + 0.85) / 3, 3),
    }


def build_strategic_operational_maturity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    insights = (truth or {}).get("strategic_runtime_insights") or []
    return {
        "intelligence_depth": len(insights) if isinstance(insights, list) else 0,
        "forecasting_enabled": bool(truth.get("operational_forecasting")),
        "advisory": True,
    }


def build_enterprise_operational_maturity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "operational_maturity_scores": build_operational_maturity_scores(truth),
        "enterprise_operational_posture": build_enterprise_operational_posture(truth),
        "runtime_strategic_outlook": build_runtime_strategic_outlook(truth),
        "operational_resilience_projection": build_operational_resilience_projection(truth),
        "runtime_resilience_maturity": build_runtime_resilience_maturity(truth),
        "ecosystem_maturity": build_ecosystem_maturity(truth),
        "strategic_operational_maturity": build_strategic_operational_maturity(truth),
    }
