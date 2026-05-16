# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_ownership import build_operator_trace_chains


def test_trace_has_steps() -> None:
    traces = build_operator_trace_chains()
    assert isinstance(traces, list)
