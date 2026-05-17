# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_operational_story_engine import build_runtime_operational_story_engine


def test_operational_story() -> None:
    out = build_runtime_operational_story_engine({"runtime_readiness_score": 0.9})
    assert out["runtime_operational_story"]["headline"]
