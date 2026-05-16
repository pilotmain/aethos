# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_evolution import apply_runtime_evolution_to_truth


def test_phase4_step3_truth_keys() -> None:
    truth: dict = {"runtime_readiness_score": 0.88, "operational_trust_score": 0.82}
    apply_runtime_evolution_to_truth(truth)
    for key in (
        "adaptive_runtime_optimization",
        "operational_intelligence_ecosystem",
        "adaptive_worker_ecosystem",
        "adaptive_operational_forecasting",
        "intelligent_runtime_evolution",
        "governance_operational_intelligence",
        "ecosystem_operational_strategy",
        "enterprise_operational_intelligence_advantage",
    ):
        assert key in truth, key
    assert truth.get("enterprise_overview", {}).get("phase") == "phase4_step6"
