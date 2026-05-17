# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Cold hydration diagnostics (Phase 4 Step 20)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.runtime_hydration import get_hydration_metrics
from app.services.mission_control.runtime_operational_throttling import build_runtime_operational_throttling


def build_runtime_hydration_diagnostics(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    hm = get_hydration_metrics()
    st = load_runtime_state()
    hm_state = st.get("hydration_metrics") or {}
    progress = truth.get("hydration_progress") or {}
    slice_times = dict(hm_state.get("slice_build_times") or progress.get("tier_build_ms") or {})
    slowest = sorted(slice_times.items(), key=lambda x: float(x[1] or 0), reverse=True)[:5]
    throttle = build_runtime_operational_throttling(truth).get("operational_throttling") or {}
    return {
        "runtime_hydration_diagnostics": {
            "cold_start_duration_ms": hm_state.get("hydration_duration_ms") or hm.get("hydration_duration_ms"),
            "slice_durations_ms": slice_times,
            "slowest_builders": [{"slice": k, "ms": v} for k, v in slowest],
            "skipped_slices": list(progress.get("skipped_slices") or []),
            "deferred_slices": list(progress.get("deferred_slices") or []),
            "cache_effectiveness": {
                "hit_rate": (truth.get("runtime_performance_intelligence") or {})
                .get("cache_efficiency", {})
                .get("hit_rate"),
                "generation_id": hm_state.get("hydration_generation_id"),
            },
            "throttling_state": throttle,
            "partial_mode": bool(progress.get("partial")),
            "tiers_complete": list(progress.get("tiers_complete") or []),
            "bounded": True,
        }
    }
