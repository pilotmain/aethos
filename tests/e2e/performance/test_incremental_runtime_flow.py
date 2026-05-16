# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth


def test_incremental_runtime_flow_keys() -> None:
    truth = build_runtime_truth(user_id=None)
    assert truth.get("hydration_metrics") is not None
    perf = truth.get("runtime_performance") or {}
    assert "hydration_latency_ms" in perf
