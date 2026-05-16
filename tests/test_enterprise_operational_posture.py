# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_evolution import build_enterprise_overview


def test_enterprise_operational_posture_overview() -> None:
    out = build_enterprise_overview({"intelligent_routing": {}, "strategic_recommendations": []})
    assert out["phase"] == "phase4_step10"
    assert "intelligent_routing" in out
