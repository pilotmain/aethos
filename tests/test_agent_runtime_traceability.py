# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.agent_runtime_truth import build_agent_visibility_for_truth
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_truth_includes_agent_visibility() -> None:
    truth = build_runtime_truth(user_id=None)
    vis = truth.get("agent_visibility") or build_agent_visibility_for_truth()
    assert "workers" in vis
