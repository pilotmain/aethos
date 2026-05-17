# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.operator_confidence_engine import build_operator_confidence


def test_operator_confidence_operational() -> None:
    out = build_operator_confidence({"runtime_readiness_score": 0.95, "hydration_progress": {}})
    assert "AethOS" in out["operator_confidence"]["summary"]
