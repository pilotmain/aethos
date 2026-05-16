# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime performance perception — operator-readable hydration (Phase 4 Step 12)."""

from __future__ import annotations

from typing import Any


def build_runtime_perception_responsiveness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    hydration = truth.get("runtime_async_hydration") or truth.get("hydration_progress") or {}
    perf = truth.get("runtime_performance_intelligence") or {}
    throttle = truth.get("runtime_operational_throttling") or {}
    resilience = truth.get("runtime_resilience") or {}
    return {
        "hydration_stage": hydration.get("current_tier") or hydration.get("max_tier") or "summary",
        "cache_health": (perf.get("cache_efficiency") or {}).get("hit_rate"),
        "stale_tolerance_seconds": 30,
        "responsiveness_score": (truth.get("operational_responsiveness") or {}).get("score"),
        "degraded_mode": resilience.get("status") in ("degraded", "recovering"),
        "summary_visible": True,
        "progressive_hydration": True,
        "operator_message": _operator_message(truth, hydration, resilience),
        "bounded": True,
    }


def _operator_message(truth: dict[str, Any], hydration: dict[str, Any], resilience: dict[str, Any]) -> str:
    if resilience.get("status") == "recovering":
        return "AethOS is recovering operational visibility — summaries load first."
    if hydration.get("partial"):
        return "Details are loading progressively — operational summary is already available."
    return "Runtime is responsive — orchestrator maintains operational calm."
