# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_runtime_truth_single_path() -> None:
    t = build_runtime_truth(user_id=None)
    assert "runtime_health" in t
    assert "routing_summary" in t
    assert "ownership_trace" in t
    assert "runtime_agents_history" in t
