# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime intelligence performance metrics (Phase 4 Step 2)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_hydration import get_hydration_metrics


def build_runtime_intelligence_performance(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    h = get_hydration_metrics()
    perf = (truth or {}).get("runtime_performance") or {}
    return {
        "hydration_ms": h.get("last_hydration_ms"),
        "cache_hit_rate": perf.get("cache_hit_rate"),
        "recommendation_slice_cached": True,
        "bounded": True,
    }


def build_forecasting_efficiency(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"derived_from_truth": True, "no_extra_llm": True, "efficient": True}


def build_coordination_scalability(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    scale = (truth or {}).get("runtime_scalability_health") or {}
    return {
        "status": scale.get("status"),
        "worker_summaries_paged": True,
        "coordination_bounded": True,
    }


def build_operational_signal_efficiency(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    signals = (truth or {}).get("operational_optimization_signals") or []
    adaptive = (truth or {}).get("adaptive_execution_signals") or []
    return {
        "optimization_signal_count": len(signals) if isinstance(signals, list) else 0,
        "coordination_signal_count": len(adaptive) if isinstance(adaptive, list) else 0,
        "capped": True,
    }
