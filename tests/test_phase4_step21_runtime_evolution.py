# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_evolution_step21 import apply_runtime_evolution_step21_to_truth


def test_phase4_step21_keys() -> None:
    truth: dict = {"routing_summary": {"fallback_used": True, "fallback_provider": "sonnet"}}
    apply_runtime_evolution_step21_to_truth(truth)
    assert truth.get("phase4_step21") is True
    assert truth.get("enterprise_ux_completed") is True
    assert truth.get("final_branding_convergence_audit")
    assert truth.get("runtime_narrative_unification")
    assert truth.get("runtime_simplification_lock", {}).get("locked") is True
    ux = truth.get("provider_routing_ux") or {}
    assert any("AethOS" in (e.get("message") or "") for e in ux.get("explanations") or [])
