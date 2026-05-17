# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_stability_coordinator import build_runtime_stability_coordinator


def test_runtime_stability() -> None:
    out = build_runtime_stability_coordinator({"runtime_readiness_score": 0.9})
    assert out["runtime_stability"]["stable"] is True
    assert out["runtime_stability_score"] >= 0.75
