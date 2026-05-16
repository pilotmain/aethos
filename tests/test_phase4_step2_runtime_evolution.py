# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_evolution import apply_runtime_evolution_to_truth


def test_phase4_step2_truth_keys() -> None:
    truth: dict = {"runtime_readiness_score": 0.88, "operational_trust_score": 0.82}
    apply_runtime_evolution_to_truth(truth)
    for key in (
        "adaptive_coordination",
        "strategic_runtime_insights",
        "worker_ecosystem_health",
        "operational_forecasting",
        "runtime_evolution_memory",
        "strategic_governance",
        "enterprise_operational_strategy",
        "runtime_intelligence_performance",
        "enterprise_operational_advantage",
    ):
        assert key in truth, key
    assert truth.get("enterprise_overview", {}).get("phase") == "phase4_step2"
