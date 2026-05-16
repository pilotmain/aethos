# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Strategic governance evolution (Phase 4 Step 2)."""

from __future__ import annotations

from typing import Any


def build_governance_maturity_progression(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    score = float((truth.get("governance_readiness") or {}).get("score") or 0.85)
    prev = len((truth.get("runtime_adaptation_history") or []))
    return {
        "current_score": score,
        "direction": "progressing" if score >= 0.8 else "maturing",
        "adaptation_cycles": prev,
        "advisory": True,
    }


def build_adaptation_governance_quality(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    gov = (truth or {}).get("runtime_evolution_governance") or {}
    return {
        "governance_visible": gov.get("governance_visible", True),
        "requires_operator_review": gov.get("requires_operator_review", True),
        "recommendation_quality": "advisory_only",
    }


def build_operational_trust_evolution(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    score = float(truth.get("operational_trust_score") or 0.8)
    learning = truth.get("adaptive_operational_learning") or {}
    return {
        "current_trust": score,
        "trust_trend": learning.get("trust_trend", "stable"),
        "escalation_count": (truth.get("runtime_escalations") or {}).get("escalation_count", 0),
    }


def build_strategic_governance(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "governance_maturity_progression": build_governance_maturity_progression(truth),
        "adaptation_governance_quality": build_adaptation_governance_quality(truth),
        "operational_trust_evolution": build_operational_trust_evolution(truth),
        "escalation_governance_trend": "stable",
        "automation_governance_maturity": (truth or {}).get("automation_reliability"),
    }
