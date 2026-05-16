# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth
from app.services.runtime_governance import build_governance_timeline


def test_discipline_and_timeline_metrics() -> None:
    build_governance_timeline(limit=8)
    truth = build_runtime_truth(user_id=None)
    scale = (truth.get("runtime_confidence") or {}).get("scalability") or {}
    disc = truth.get("runtime_discipline") or {}
    assert "event_buffer_size" in disc
    assert "truth_build_ms" in scale or disc.get("last_truth_build_ms") is not None
