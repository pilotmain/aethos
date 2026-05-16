# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_startup_experience import build_runtime_startup_experience


def test_runtime_startup_experience() -> None:
    out = build_runtime_startup_experience({"hydration_progress": {"partial": True}})
    exp = out["runtime_startup_experience"]
    assert exp["no_white_screen"] is True
    assert exp["current_stage"]["label"]
