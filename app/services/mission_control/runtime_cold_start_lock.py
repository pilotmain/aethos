# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Cold hydration optimization lock — summary-first availability (Phase 4 Step 14)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_hydration import get_hydration_metrics


def _progress_percent(progress: dict[str, Any]) -> float:
    tiers = progress.get("tiers_complete") or []
    if not tiers:
        return 0.35 if progress.get("partial") else 1.0
    order = ("critical", "operational", "advisory", "background")
    done = sum(1 for t in order if t in tiers)
    return round(min(1.0, 0.25 + done * 0.2), 3)


def build_runtime_readiness_progress(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    progress = truth.get("hydration_progress") or {}
    partial = bool(progress.get("partial", True))
    return {
        "readiness_progress": {
            "partial": partial,
            "max_tier": progress.get("max_tier") or "operational",
            "tiers_complete": list(progress.get("tiers_complete") or [])[:6],
            "percent_estimate": _progress_percent(progress),
            "office_alive": True,
            "summary_first": True,
            "feels_alive": True,
            "bounded": True,
        }
    }


def build_runtime_cold_start(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    hm = get_hydration_metrics()
    perf = truth.get("runtime_performance_intelligence") or {}
    tier_ms = (truth.get("hydration_progress") or {}).get("tier_build_ms") or {}
    critical_ms = tier_ms.get("critical") if isinstance(tier_ms, dict) else None
    cold_ms = float(hm.get("hydration_duration_ms") or hm.get("last_hydration_ms") or 0)
    warm_ms = float(hm.get("last_hydration_ms") or 0)
    return {
        "runtime_cold_start": {
            "cold_hydration_duration_ms": cold_ms or None,
            "warm_hydration_duration_ms": warm_ms or None,
            "partial_readiness_time_ms": critical_ms,
            "office_initial_render_ms": critical_ms,
            "runtime_responsiveness_score": perf.get("operational_responsiveness_score"),
            "cold_start_active": bool((truth.get("hydration_progress") or {}).get("partial")),
            "summary_first_rendering": True,
            "bounded": True,
        }
    }


def build_runtime_partial_availability(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    partial = bool((truth.get("hydration_progress") or {}).get("partial"))
    status = (truth.get("runtime_resilience") or {}).get("status") or "healthy"
    available = ["office_summary", "orchestrator", "recovery_center", "cached_truth", "advisories"]
    if not partial and status == "healthy":
        available.extend(["governance", "workers", "routing", "marketplace", "full_timeline"])
    deferred: list[str] = []
    if partial:
        deferred = ["full_governance_timeline", "deep_intelligence_slices", "background_eras"]
    return {
        "runtime_partial_availability": {
            "partial_mode": partial or status in ("degraded", "partial", "stale"),
            "available_surfaces": available[:12],
            "deferred_surfaces": deferred[:8],
            "feels_alive": True,
            "not_frozen": True,
            "bounded": True,
        }
    }
