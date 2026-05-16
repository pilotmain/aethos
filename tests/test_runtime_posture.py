# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_awareness import build_runtime_awareness


def test_runtime_posture_matrix() -> None:
    out = build_runtime_awareness({"operational_pressure": {"level": "low"}, "runtime_calmness": {"calm_score": 0.9}})
    assert out["operational_stability_matrix"]["stable"] is True
