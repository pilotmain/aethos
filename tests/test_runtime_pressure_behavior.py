# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.enterprise_operational_discipline import build_enterprise_operational_discipline


def test_runtime_pressure_behavior() -> None:
    out = build_enterprise_operational_discipline(
        {"operational_pressure": {"level": "high"}, "runtime_operational_throttling": {"active": True, "deferred_slices": 2}}
    )
    disc = out["enterprise_operational_discipline"]
    assert disc["operational_pressure_level"] == "high"
    assert disc["deferred_workload_count"] == 2
