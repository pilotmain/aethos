# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_calmness_integrity import build_runtime_calmness_integrity


def test_calmness_integrity() -> None:
    out = build_runtime_calmness_integrity(
        {"runtime_calmness": {"feels_calm": True, "calm_score": 0.9}, "runtime_escalations": {"escalation_count": 0}}
    )
    assert out["critical_escalations_visible"] is True
    assert "calmness_integrity" in out
