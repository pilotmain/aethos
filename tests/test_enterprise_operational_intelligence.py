# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_evolution_step3 import build_enterprise_intelligence_summary


def test_enterprise_intelligence_summary() -> None:
    out = build_enterprise_intelligence_summary(
        {
            "ecosystem_operational_health": {"status": "healthy"},
            "runtime_optimization_quality": {"score": 0.9},
            "governance_operational_intelligence": {},
        }
    )
    assert out.get("phase") == "phase4_step3"
