# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_evolution_step7 import apply_runtime_evolution_step7_to_truth


def test_phase4_step7_truth_keys() -> None:
    truth: dict = {"operational_pressure": {"level": "low"}}
    apply_runtime_evolution_step7_to_truth(truth, user_id="u7")
    for key in (
        "runtime_operational_throttling",
        "runtime_performance_intelligence",
        "operational_responsiveness",
        "office_operational_stream",
        "phase4_step7",
    ):
        assert key in truth, key
