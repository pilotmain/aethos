# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.strategic_governance import build_strategic_governance


def test_strategic_governance_progression() -> None:
    out = build_strategic_governance({"governance_readiness": {"score": 0.9}})
    assert "governance_maturity_progression" in out
