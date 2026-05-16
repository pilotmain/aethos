# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.adaptive_runtime_optimization import build_adaptive_runtime_optimization


def test_adaptive_runtime_optimization_advisory() -> None:
    out = build_adaptive_runtime_optimization({})
    assert out.get("advisory_first") is True
    assert out.get("governance_aware") is True
