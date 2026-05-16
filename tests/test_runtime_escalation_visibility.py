# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_escalations import build_runtime_escalations
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_escalations_on_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    assert truth.get("runtime_escalations")
    assert truth.get("escalation_visibility")
    assert truth.get("escalation_history") is not None


def test_escalation_types_list() -> None:
    esc = build_runtime_escalations({})
    assert "types_present" in esc
