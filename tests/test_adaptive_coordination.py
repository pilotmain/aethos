# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.adaptive_coordination import build_adaptive_coordination


def test_adaptive_coordination_advisory() -> None:
    out = build_adaptive_coordination({"operational_pressure": {"queue_pressure": True}})
    assert out.get("advisory_first") is True
    assert "adaptive_execution_signals" in out
