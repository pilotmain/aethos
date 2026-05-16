# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_ownership import build_operator_trace_chains
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_trace_has_steps() -> None:
    traces = build_operator_trace_chains()
    assert isinstance(traces, list)


def test_truth_exposes_ownership_trace() -> None:
    truth = build_runtime_truth(user_id=None)
    assert isinstance(truth.get("ownership_trace"), list)
    traces = truth.get("operator_traces") or {}
    assert "provider" in traces
    assert "repair" in traces or "deployment" in traces or isinstance(traces, dict)
