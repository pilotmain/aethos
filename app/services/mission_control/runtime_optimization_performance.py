# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime optimization performance metrics (Phase 4 Step 3)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_hydration import get_hydration_metrics


def build_runtime_optimization_performance(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    h = get_hydration_metrics()
    intel = (truth or {}).get("runtime_intelligence_performance") or {}
    return {
        "hydration_ms": h.get("last_hydration_ms"),
        "cache_hit_rate": intel.get("cache_hit_rate"),
        "optimization_overhead_bounded": True,
    }


def build_ecosystem_scalability_quality(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return (truth or {}).get("coordination_scalability") or {"coordination_bounded": True}


def build_operational_intelligence_responsiveness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    perf = (truth or {}).get("operational_performance_completion") or {}
    mc = perf.get("mission_control_responsiveness") or {}
    return {
        "within_target": mc.get("within_target", False),
        "slice_apis": True,
    }


def build_runtime_signal_optimization(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    eff = (truth or {}).get("operational_signal_efficiency") or {}
    opt = (truth or {}).get("operational_efficiency_signals") or []
    return {
        **eff,
        "optimization_signals": len(opt) if isinstance(opt, list) else 0,
        "capped": True,
    }
