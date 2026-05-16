# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.operator_ownership import build_operator_ownership_summary
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_ownership_summary() -> None:
    truth = build_runtime_truth(user_id=None)
    own = build_operator_ownership_summary(truth, user_id="test-user")
    assert own.get("runtime_owner") == "AethOS Orchestrator"
    assert "deployment_count" in own
