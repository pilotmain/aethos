# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.operational_intelligence_ecosystem import build_operational_intelligence_ecosystem


def test_operational_intelligence_ecosystem() -> None:
    out = build_operational_intelligence_ecosystem({"worker_ecosystem_health": {"status": "healthy"}})
    assert out.get("bounded") is True
    assert "ecosystem_coordination" in out
