# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime startup experience — progressive hydration stages (Phase 4 Step 16)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_cold_start_lock import build_runtime_readiness_progress
from app.services.mission_control.runtime_hydration import get_hydration_metrics


HYDRATION_STAGES = (
    {"id": "starting", "label": "Starting runtime"},
    {"id": "workers", "label": "Loading workers"},
    {"id": "memory", "label": "Loading operational memory"},
    {"id": "governance", "label": "Loading governance timeline"},
    {"id": "intelligence", "label": "Loading runtime intelligence"},
    {"id": "ready", "label": "Runtime ready"},
)

ENTERPRISE_STARTUP_STAGES = (
    {"id": "initializing", "label": "Initializing"},
    {"id": "core_ready", "label": "Core ready"},
    {"id": "office_ready", "label": "Office ready"},
    {"id": "runtime_ready", "label": "Runtime ready"},
    {"id": "intelligence_ready", "label": "Intelligence ready"},
    {"id": "enterprise_ready", "label": "Enterprise ready"},
)


def build_runtime_startup_experience(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    progress = build_runtime_readiness_progress(truth).get("readiness_progress") or {}
    tiers = list(progress.get("tiers_complete") or [])
    pct = float(progress.get("percent_estimate") or 0.35)
    stage_idx = min(len(HYDRATION_STAGES) - 1, int(pct * (len(HYDRATION_STAGES) - 1)))
    current = HYDRATION_STAGES[stage_idx]
    partial = bool(progress.get("partial"))
    ent_idx = min(len(ENTERPRISE_STARTUP_STAGES) - 1, int(pct * (len(ENTERPRISE_STARTUP_STAGES) - 1)))
    enterprise_stage = ENTERPRISE_STARTUP_STAGES[ent_idx]
    return {
        "runtime_startup_experience": {
            "current_stage": current,
            "enterprise_stage": enterprise_stage,
            "enterprise_stages": ENTERPRISE_STARTUP_STAGES,
            "stages": HYDRATION_STAGES,
            "readiness_percent": pct,
            "partial_mode": partial,
            "degraded_mode": (truth.get("runtime_resilience") or {}).get("status") not in (None, "healthy"),
            "cached_snapshot_fallback": bool((truth.get("runtime_resilience") or {}).get("using_cached_truth")),
            "partial_availability_notice": "Summaries available while full intelligence hydrates." if partial else None,
            "no_white_screen": True,
            "tiers_complete": tiers,
            "bounded": True,
        }
    }


def build_runtime_hydration_stages(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    hm = get_hydration_metrics()
    tier_ms = (truth.get("hydration_progress") or {}).get("tier_build_ms") or {}
    stages = []
    for s in HYDRATION_STAGES[:-1]:
        stages.append({**s, "complete": s["id"] in ("starting",) or bool(tier_ms)})
    stages.append({**HYDRATION_STAGES[-1], "complete": not (truth.get("hydration_progress") or {}).get("partial")})
    return {"runtime_hydration_stages": {"stages": stages, "metrics": hm, "bounded": True}}


def build_runtime_readiness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    startup = build_runtime_startup_experience(truth)
    return {
        "runtime_readiness": {
            "ready": not startup["runtime_startup_experience"].get("partial_mode"),
            "percent": startup["runtime_startup_experience"].get("readiness_percent"),
            "stage": startup["runtime_startup_experience"].get("current_stage"),
            "office_first": True,
            "bounded": True,
        }
    }
