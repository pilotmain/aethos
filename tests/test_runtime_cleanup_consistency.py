# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_intelligence import _truth
from app.services.mission_control.runtime_panels import build_runtime_panels


def test_panels_use_cached_truth() -> None:
    t1 = _truth(None)
    panels = build_runtime_panels(None)
    assert panels.get("runtime_health") == t1.get("runtime_health")
