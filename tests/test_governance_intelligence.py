# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.governance_intelligence import build_governance_operational_intelligence


def test_governance_operational_intelligence() -> None:
    out = build_governance_operational_intelligence({"governance_readiness": {"score": 0.9}})
    assert "intelligent_governance_progression" in out
