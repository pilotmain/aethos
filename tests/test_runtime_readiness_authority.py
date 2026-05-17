# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_readiness_authority import READINESS_STATES, build_runtime_readiness_authority


def test_readiness_authority_operational() -> None:
    truth = {"runtime_readiness_score": 0.92, "hydration_progress": {"partial": False}}
    out = build_runtime_readiness_authority(truth)["runtime_readiness_authority"]
    assert out["state"] in READINESS_STATES
    assert out["authoritative"] is True
    assert out.get("enterprise_ready") is True
