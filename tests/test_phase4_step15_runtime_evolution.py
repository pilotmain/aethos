# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_evolution_step15 import apply_runtime_evolution_step15_to_truth


def test_phase4_step15_keys() -> None:
    truth: dict = {"release_candidate": True}
    apply_runtime_evolution_step15_to_truth(truth)
    assert truth.get("phase4_step15") is True
    assert truth.get("first_impression_locked") is True
    assert truth.get("setup_continuity")
    assert truth.get("setup_experience", {}).get("conversational") is True
