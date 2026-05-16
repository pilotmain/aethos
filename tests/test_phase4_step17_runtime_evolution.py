# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_evolution_step17 import apply_runtime_evolution_step17_to_truth


def test_phase4_step17_keys() -> None:
    truth: dict = {}
    apply_runtime_evolution_step17_to_truth(truth)
    assert truth.get("phase4_step17") is True
    assert truth.get("installer_interaction_locked") is True
