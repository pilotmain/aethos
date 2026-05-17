# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_evolution_step22 import apply_runtime_evolution_step22_to_truth
from app.services.mission_control.runtime_integrity_certification import build_runtime_integrity_certification


def test_integrity_certification() -> None:
    truth = {"runtime_readiness_score": 0.95, "hydration_progress": {}, "phase4_step21": True}
    apply_runtime_evolution_step22_to_truth(truth)
    cert = truth["runtime_integrity_certification"]
    assert "integrity_score" in cert
    assert cert.get("phase") == "phase4_step22"
