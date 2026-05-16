# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.mission_control_cohesion import build_cohesion_report
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_cohesion_report_cohesive() -> None:
    truth = build_runtime_truth(user_id=None)
    report = build_cohesion_report(truth)
    assert report.get("cohesive") is True
    assert report.get("office_has_orchestrator") is True
