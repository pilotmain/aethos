# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_truth_consistency import build_runtime_truth_consistency


def test_truth_consistency() -> None:
    truth = {"runtime_resilience": {}, "hydration_progress": {}, "runtime_process_supervision": {}}
    out = build_runtime_truth_consistency(truth)["runtime_truth_consistency"]
    assert "truth_consistency_score" in out
