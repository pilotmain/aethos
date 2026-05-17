# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_evolution_step18 import apply_runtime_evolution_step18_to_truth


def test_phase4_step18_keys() -> None:
    truth: dict = {}
    apply_runtime_evolution_step18_to_truth(truth)
    assert truth.get("phase4_step18") is True
    assert truth.get("process_supervision_locked") is True
    assert "runtime_ownership" in truth
