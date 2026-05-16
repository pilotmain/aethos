# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Intelligent runtime recommendations (Phase 4 Step 5)."""

from __future__ import annotations

from typing import Any


def _advisory(
    *,
    title: str,
    why: str,
    impact: str,
    confidence: float,
    risk: str,
    systems: list[str],
    next_step: str,
    approval: bool = False,
) -> dict[str, Any]:
    return {
        "title": title,
        "why_this_matters": why,
        "operational_impact": impact,
        "confidence_score": confidence,
        "risk_level": risk,
        "affected_systems": systems,
        "suggested_next_step": next_step,
        "explainability_summary": why,
        "governance_visible": True,
        "approval_required": approval,
        "advisory_only": True,
    }


def build_enterprise_runtime_advisories(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    truth = truth or {}
    out: list[dict[str, Any]] = []
    if (truth.get("operational_pressure") or {}).get("level") == "high":
        out.append(
            _advisory(
                title="Reduce runtime pressure",
                why="Queue and worker pressure elevated.",
                impact="Stabilizes execution and routing.",
                confidence=0.82,
                risk="medium",
                systems=["workers", "routing"],
                next_step="Review worker concurrency and routing fallback.",
            )
        )
    if (truth.get("routing_summary") or {}).get("fallback_used"):
        out.append(
            _advisory(
                title="Review provider fallback",
                why="Fallback routing active.",
                impact="May increase latency or cost.",
                confidence=0.78,
                risk="low",
                systems=["providers", "routing"],
                next_step="Inspect provider health and routing preference.",
            )
        )
    return out[:8]


def build_recommendation_quality(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"score": 0.85, "context_aware": True, "bounded": True}


def build_operational_guidance(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"mode": "advisory", "operator_owned": True}


def build_runtime_advisory_engine(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    advisories = build_enterprise_runtime_advisories(truth)
    return {
        "strategic_recommendations": advisories,
        "enterprise_runtime_advisories": advisories,
        "recommendation_quality": build_recommendation_quality(truth),
        "operational_guidance": build_operational_guidance(truth),
        "runtime_advisory_engine": {"active": True, "count": len(advisories)},
    }
