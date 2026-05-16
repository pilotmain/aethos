# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_performance_intelligence import build_runtime_performance_intelligence


def test_performance_intelligence_score() -> None:
    out = build_runtime_performance_intelligence({"runtime_performance": {"hydration_latency_ms": 100}})
    assert "operational_responsiveness_score" in out
    assert isinstance(out.get("recommendations"), list)
