# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_evolution_step5 import apply_runtime_evolution_step5_to_truth

_STEP5_KEYS = (
    "intelligent_routing",
    "adaptive_provider_selection",
    "runtime_provider_strategy",
    "routing_effectiveness",
    "operational_recovery_state",
    "degradation_signals",
    "runtime_stabilization",
    "operational_memory_intelligence",
    "strategic_operational_memory",
    "runtime_awareness",
    "operational_stability_matrix",
    "operational_experience",
    "runtime_focus_mode",
    "strategic_runtime_planning",
    "intelligent_worker_ecosystem",
    "operational_continuity_engine",
    "strategic_recommendations",
    "governance_intelligence",
    "phase4_step5",
)


def test_phase4_step5_truth_keys() -> None:
    truth: dict = {
        "runtime_readiness_score": 0.88,
        "operational_trust_score": 0.82,
        "routing_summary": {"primary_provider": "openai", "fallback_used": False},
    }
    apply_runtime_evolution_step5_to_truth(truth)
    for key in _STEP5_KEYS:
        assert key in truth, key
    assert truth["intelligent_routing"].get("advisory_first") is True
    assert truth["governance_intelligence"].get("explainability_integrity", {}).get("no_hidden_autonomy") is True


def test_phase4_step6_keys_via_step5_apply() -> None:
    from app.services.mission_control.runtime_evolution_step6 import apply_runtime_evolution_step6_to_truth

    truth: dict = {"office": {}}
    apply_runtime_evolution_step6_to_truth(truth)
    assert truth.get("phase4_step6") is True
    assert "runtime_truth_integrity" in truth
    assert "runtime_recovery_center" in truth
