# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_cohesion import build_unified_operational_timeline
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_unified_timeline_searchable() -> None:
    tl = build_unified_operational_timeline(
        {"runtime_recommendations": {"recommendations": []}, "operational_risk": {"risk_signals": []}},
        limit=30,
    )
    assert "timeline" in tl
    assert "searchable_kinds" in tl
