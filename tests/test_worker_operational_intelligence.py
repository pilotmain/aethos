# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_truth_includes_worker_intel() -> None:
    truth = build_runtime_truth(user_id=None)
    assert "worker_deliverables" in truth
    assert "worker_effectiveness" in truth
