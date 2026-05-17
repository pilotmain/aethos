# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_operational_authority import build_runtime_operational_authority


def test_operational_authority_partial_hydration() -> None:
    truth = {"runtime_readiness_score": 0.7, "hydration_progress": {"partial": True}}
    out = build_runtime_operational_authority(truth)
    assert out["operational_authority"]["hydration_partial"] is True
    assert "preparing enterprise runtime" in out["operational_authority"]["operator_message"].lower()
