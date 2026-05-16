# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_ownership import build_all_operator_traces


def test_all_operator_traces_keys() -> None:
    traces = build_all_operator_traces()
    assert "ownership" in traces
    assert "repair" in traces
    assert "deployment" in traces
    assert "provider" in traces
