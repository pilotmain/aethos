# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.operational_recovery_engine import build_operational_recovery_state


def test_runtime_recovery_signals() -> None:
    out = build_operational_recovery_state({"operational_pressure": {"level": "high"}})
    assert any(s.get("kind") == "runtime_saturation" for s in out["degradation_signals"])
