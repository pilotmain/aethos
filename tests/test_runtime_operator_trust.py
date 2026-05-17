# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_production_certification import build_runtime_operator_trust


def test_operator_trust() -> None:
    out = build_runtime_operator_trust({"runtime_readiness_score": 0.95, "hydration_progress": {}})
    assert "trusted" in out["runtime_operator_trust"]
