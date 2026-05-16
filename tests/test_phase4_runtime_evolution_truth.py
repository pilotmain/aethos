# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.runtime_evolution import apply_runtime_evolution_to_truth


def test_apply_runtime_evolution_truth_keys() -> None:
    truth: dict = {
        "runtime_readiness_score": 0.88,
        "operational_trust_score": 0.82,
        "governance_readiness": {"score": 0.9},
    }
    apply_runtime_evolution_to_truth(truth)
    for key in (
        "adaptive_runtime_intelligence",
        "adaptive_coordination",
        "worker_learning_state",
        "worker_ecosystem_health",
        "automation_operational_effectiveness",
        "strategic_runtime_alerts",
        "strategic_runtime_insights",
        "enterprise_operational_memory",
        "runtime_evolution_memory",
        "runtime_evolution_governance",
        "enterprise_operational_maturity",
        "strategic_differentiation_summary",
        "enterprise_overview",
    ):
        assert key in truth, key
    assert truth.get("enterprise_overview", {}).get("phase") == "phase4_step9"
