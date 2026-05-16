# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.governance_intelligence_runtime import build_governance_intelligence_runtime


def test_governance_intelligence_runtime() -> None:
    out = build_governance_intelligence_runtime({})
    assert out["explainability_integrity"]["operator_visible"] is True
