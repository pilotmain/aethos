# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_assurance_engine import build_runtime_assurance_engine


def test_runtime_assurance() -> None:
    out = build_runtime_assurance_engine({"runtime_readiness_score": 0.95, "hydration_progress": {}})
    assert "AethOS" in out["runtime_assurance"]["summary"]
