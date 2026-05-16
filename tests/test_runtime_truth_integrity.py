# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_truth_integrity import validate_truth_integrity


def test_truth_integrity_score() -> None:
    out = validate_truth_integrity({"office": {}, "routing_summary": {}})
    assert out["truth_integrity_score"] >= 0.8
    assert out["cohesive"] is True
