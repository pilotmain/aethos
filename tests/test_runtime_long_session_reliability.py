# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_long_session_reliability import build_runtime_long_session_reliability


def test_long_session() -> None:
    out = build_runtime_long_session_reliability({"runtime_readiness_score": 0.92})["runtime_long_session_reliability"]
    assert "AethOS" in out["operator_summary"]
