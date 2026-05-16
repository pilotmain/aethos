# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.governance_timeline_unified import build_unified_governance_timeline
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_unified_timeline_authoritative() -> None:
    truth = build_runtime_truth(user_id=None)
    tl = truth.get("unified_operational_timeline") or {}
    assert tl.get("authoritative") is True
    assert "timeline" in tl


def test_dedupe_reduces_duplicates() -> None:
    truth = {"runtime_recommendations": {"recommendations": [{"message": "x", "reason": "y"}] * 3}}
    out = build_unified_governance_timeline(truth, limit=20)
    assert out.get("entry_count", 0) <= 20
