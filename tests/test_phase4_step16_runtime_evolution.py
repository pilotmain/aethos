# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_evolution_step16 import apply_runtime_evolution_step16_to_truth


def test_phase4_step16_keys() -> None:
    truth: dict = {}
    apply_runtime_evolution_step16_to_truth(truth)
    assert truth.get("phase4_step16") is True
    assert truth.get("enterprise_setup_finalized") is True
    assert truth.get("runtime_startup_experience")
