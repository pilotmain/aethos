# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.strategic_runtime_intelligence import build_strategic_runtime_insights


def test_strategic_runtime_insights_bounded() -> None:
    insights = build_strategic_runtime_insights({"runtime_readiness_score": 0.9})
    assert isinstance(insights, list)
    assert len(insights) <= 8
