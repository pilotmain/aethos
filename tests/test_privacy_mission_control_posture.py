# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_truth_privacy_posture() -> None:
    t = build_runtime_truth(user_id=None)
    assert "privacy_posture" in t
    assert t["privacy_posture"].get("privacy_posture")
