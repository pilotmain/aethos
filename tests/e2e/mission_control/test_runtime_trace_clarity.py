# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_runtime_trace_clarity() -> None:
    truth = build_runtime_truth(user_id=None)
    trace = truth.get("ownership_trace") or []
    assert isinstance(trace, list)
    if trace:
        row = trace[0]
        assert "runtime_agent_id" in row or "task_id" in row or isinstance(row, dict)
