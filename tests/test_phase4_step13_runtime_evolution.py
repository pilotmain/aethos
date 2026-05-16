# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_evolution_step13 import apply_runtime_evolution_step13_to_truth


def test_phase4_step13_keys() -> None:
    truth: dict = {}
    apply_runtime_evolution_step13_to_truth(truth)
    assert truth.get("phase4_step13") is True
    assert truth.get("launch_ready") is True
    assert truth.get("runtime_duplication_lock")
    assert truth.get("launch_readiness_certification", {}).get("launch_ready") is True
    assert truth.get("runtime_calmness_metrics", {}).get("calmness_score") is not None
