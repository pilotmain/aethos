# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_governance_completion_summaries() -> None:
    truth = build_runtime_truth(user_id=None)
    assert truth.get("governance_operational_summary")
    assert truth.get("runtime_accountability_summary")
    assert truth.get("escalation_operational_summary")
