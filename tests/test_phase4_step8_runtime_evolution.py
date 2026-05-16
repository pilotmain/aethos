# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_evolution_step8 import apply_runtime_evolution_step8_to_truth


def test_phase4_step8_truth_keys() -> None:
    truth: dict = {}
    apply_runtime_evolution_step8_to_truth(truth)
    for key in (
        "runtime_long_horizon",
        "enterprise_runtime_summaries",
        "runtime_operational_partitions",
        "governance_operational_index",
        "runtime_calmness_integrity",
        "worker_operational_lifecycle",
        "production_runtime_posture",
        "phase4_step8",
    ):
        assert key in truth, key
