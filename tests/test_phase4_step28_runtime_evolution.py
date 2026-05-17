# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_evolution_step28 import apply_runtime_evolution_step28_to_truth


def test_phase4_step28() -> None:
    truth = {
        "runtime_readiness_score": 0.92,
        "launch_stabilized": True,
        "enterprise_runtime_finalized": True,
        "setup_ready_state_locked": True,
    }
    apply_runtime_evolution_step28_to_truth(truth)
    assert truth.get("phase4_step28") is True
    assert truth.get("runtime_launch_experience")
