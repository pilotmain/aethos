# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.runtime_strategy_awareness import build_runtime_strategy_awareness


def test_runtime_strategy_awareness_keys() -> None:
    out = build_runtime_strategy_awareness({"runtime_readiness_score": 0.9})
    assert "strategic_runtime_alerts" in out
    assert "operational_trajectory_summary" in out
    assert out["operational_trajectory_summary"].get("direction") == "stable"
