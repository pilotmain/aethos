# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_operational_throttling import build_runtime_operational_throttling


def test_throttling_under_pressure() -> None:
    out = build_runtime_operational_throttling({"operational_pressure": {"level": "high"}})
    assert out["active"] is True
    assert "critical_failures" in str(out.get("never_suppresses"))
