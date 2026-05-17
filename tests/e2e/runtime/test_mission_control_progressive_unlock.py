# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_launch_experience import build_runtime_launch_experience


def test_mission_control_progressive_unlock() -> None:
    blob = build_runtime_launch_experience({"runtime_readiness_score": 0.6})
    assert blob["runtime_launch_progress"]["percent"] >= 0
