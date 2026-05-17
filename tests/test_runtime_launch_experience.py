# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_launch_experience import build_runtime_launch_experience, LAUNCH_STAGES


def test_runtime_launch_experience() -> None:
    blob = build_runtime_launch_experience({"runtime_readiness_score": 0.85})
    assert len(blob["runtime_launch_experience"]["stages"]) == len(LAUNCH_STAGES)
