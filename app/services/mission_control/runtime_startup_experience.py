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
    {"id": "initializing_runtime", "label": "Initializing runtime"},
    {"id": "loading_operational_memory", "label": "Loading operational memory"},
    {"id": "restoring_worker_context", "label": "Restoring worker context"},
    {"id": "warming_enterprise_intelligence", "label": "Warming enterprise intelligence"},
    {"id": "synchronizing_runtime_state", "label": "Synchronizing runtime state"},
    {"id": "finalizing_operational_surfaces", "label": "Finalizing operational surfaces"},
    {"id": "enterprise_ready", "label": "Enterprise ready"},
)

# Legacy aliases for MC clients on earlier step contracts
ENTERPRISE_STARTUP_STAGES_LEGACY = (
    {"id": "initializing", "label": "Initializing"},
    {"id": "office_ready", "label": "Office ready"},
    {"id": "runtime_ready", "label": "Runtime ready"},
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
    unlocked = ["office", "runtime_overview", "recovery"]
    if pct >= 0.5:
        unlocked.append("runtime_supervision")
    if pct >= 0.75:
        unlocked.extend(["governance", "runtime_intelligence"])
    if not partial:
        unlocked.extend(["marketplace", "providers", "executive_overview"])
    return {
        "runtime_startup_experience": {
            "current_stage": current,
            "enterprise_stage": enterprise_stage,
            "enterprise_stages": ENTERPRISE_STARTUP_STAGES,
            "enterprise_stages_legacy": ENTERPRISE_STARTUP_STAGES_LEGACY,
            "stages": HYDRATION_STAGES,
            "readiness_percent": pct,
            "partial_mode": partial,
            "progressive_surface_unlock": unlocked,
            "alive_progressive_operational": True,
            "degraded_mode": (truth.get("runtime_resilience") or {}).get("status") not in (None, "healthy"),
            "cached_snapshot_fallback": bool((truth.get("runtime_resilience") or {}).get("using_cached_truth")),
            "partial_availability_notice": (
                "Core orchestration is available while enterprise intelligence finishes loading."
                if partial
                else None
            ),
            "no_white_screen": True,
            "tiers_complete": tiers,
            "phase": "phase4_step23",
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
