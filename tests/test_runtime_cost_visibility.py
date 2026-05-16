# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_confidence import build_runtime_cost_visibility
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_runtime_cost_note() -> None:
    truth = build_runtime_truth(user_id=None)
    cost = build_runtime_cost_visibility(truth)
    assert "note" in cost
    assert "billing" in str(cost.get("note")).lower()
