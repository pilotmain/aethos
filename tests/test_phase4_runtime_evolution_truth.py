# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.runtime_evolution import build_enterprise_overview
from app.services.mission_control.runtime_evolution_step21 import apply_runtime_evolution_step21_to_truth


def test_apply_runtime_evolution_step21_truth_keys() -> None:
    truth: dict = {
        "runtime_readiness_score": 0.88,
        "operational_trust_score": 0.82,
        "governance_readiness": {"score": 0.9},
    }
    apply_runtime_evolution_step21_to_truth(truth)
    truth["enterprise_overview"] = build_enterprise_overview(truth)
    for key in (
        "final_branding_convergence_audit",
        "runtime_narrative_unification",
        "runtime_simplification_lock",
        "provider_routing_ux",
        "runtime_calmness_lock",
        "operator_language_system",
        "enterprise_overview",
    ):
        assert key in truth, key
    assert truth.get("phase4_step21") is True
    assert truth.get("enterprise_overview", {}).get("phase") == "phase4_step21"
