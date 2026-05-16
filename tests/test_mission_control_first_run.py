# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.mission_control_first_run import build_mission_control_first_run


def test_first_run_steps() -> None:
    out = build_mission_control_first_run({"runtime_readiness_score": 0.9})
    steps = out["mission_control_first_run"]["steps"]
    assert len(steps) >= 5
    assert out["mission_control_first_run"]["tone"] == "premium_calm"
