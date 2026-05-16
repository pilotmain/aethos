# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_operational_partitions import build_runtime_operational_partitions


def test_partitions_live() -> None:
    out = build_runtime_operational_partitions({"office": {}, "intelligent_routing": {"advisory_first": True}})
    assert out["live"]["active"] is True
    assert out["intelligence"]["routing"] is True
