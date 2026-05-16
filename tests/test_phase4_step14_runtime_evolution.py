# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_evolution_step14 import apply_runtime_evolution_step14_to_truth


def test_phase4_step14_keys() -> None:
    truth: dict = {"launch_ready": True}
    apply_runtime_evolution_step14_to_truth(truth)
    assert truth.get("phase4_step14") is True
    assert truth.get("release_candidate") is True
    assert truth.get("operational_freeze_lock")
    assert truth.get("release_candidate_certification", {}).get("release_candidate") is True
