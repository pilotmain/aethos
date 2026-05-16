# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_optimization_performance import build_runtime_optimization_performance


def test_runtime_optimization_performance() -> None:
    out = build_runtime_optimization_performance({})
    assert out.get("optimization_overhead_bounded") is True
