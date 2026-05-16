# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.adaptive_runtime_intelligence import build_adaptive_runtime_intelligence


def test_adaptive_runtime_intelligence_advisory_bounded() -> None:
    out = build_adaptive_runtime_intelligence({"operational_trust_score": 0.9})
    assert out.get("advisory_first") is True
    assert out.get("explainable") is True
    assert "operational_optimization_signals" in out
    assert "adaptive_operational_learning" in out
    assert out["adaptive_operational_learning"].get("learning_mode") == "advisory_only"
