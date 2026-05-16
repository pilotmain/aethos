# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.runtime_intelligence import build_runtime_metrics_slice


def test_runtime_metrics_slice_shape() -> None:
    out = build_runtime_metrics_slice("user1")
    metrics = out.get("metrics") or {}
    assert "task_throughput" in metrics
    assert "runtime_reliability" in metrics
