# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_discipline_completion_keys() -> None:
    truth = build_runtime_truth(user_id=None)
    assert truth.get("runtime_discipline_completion")
    assert truth.get("simplification_progress")
    assert truth.get("operational_signal_health")
    assert truth.get("calmness_lock")
