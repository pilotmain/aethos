# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime evolution performance metrics (Phase 4 Step 1)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_hydration import get_hydration_metrics


def build_runtime_evolution_performance(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    perf = truth.get("operational_performance_completion") or {}
    h = get_hydration_metrics()
    return {
        "hydration_optimization_quality": perf.get("runtime_hydration_efficiency"),
        "payload_efficiency": perf.get("runtime_payload_efficiency"),
        "phase4_overhead_ms": 0,
        "bounded": True,
    }


def build_operational_scalability_metrics(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    scale = truth.get("runtime_scalability_health") or {}
    return {
        "status": scale.get("status"),
        "event_buffer_size": scale.get("event_buffer_size"),
        "slice_cache_hit_rate": scale.get("slice_cache_hit_rate"),
    }


def build_hydration_optimization_quality(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    perf = build_runtime_evolution_performance(truth)
    return {"score": perf.get("hydration_optimization_quality"), "target": 0.85}
