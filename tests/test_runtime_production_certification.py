# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_evolution_step23 import apply_runtime_evolution_step23_to_truth
from app.services.mission_control.runtime_production_certification import build_runtime_production_certification


def test_production_certification() -> None:
    truth = {
        "runtime_readiness_score": 0.95,
        "hydration_progress": {},
        "runtime_resilience": {},
        "runtime_process_supervision": {},
        "operator_facing_branding_locked": True,
    }
    apply_runtime_evolution_step23_to_truth(truth)
    cert = truth["runtime_production_certification"]
    assert "production_grade" in cert
    assert cert.get("phase") == "phase4_step23"
