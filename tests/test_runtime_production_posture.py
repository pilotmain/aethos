# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_production_posture import build_production_runtime_posture


def test_production_posture_score() -> None:
    out = build_production_runtime_posture(
        {
            "runtime_performance_intelligence": {"operational_responsiveness_score": 0.9},
            "runtime_resilience": {"status": "healthy"},
            "runtime_truth_integrity": {"truth_integrity_score": 0.9},
        }
    )
    assert out["sustained_operation_score"] >= 0.75
