# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_panels_from_truth, build_runtime_truth


def test_panels_derived_from_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    panels = build_runtime_panels_from_truth(truth)
    assert panels["runtime_health"] == truth["runtime_health"]
