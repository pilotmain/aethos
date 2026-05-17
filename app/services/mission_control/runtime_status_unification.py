# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Unified runtime operational status (Phase 4 Step 22)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_operational_authority import build_runtime_operational_authority
from app.services.mission_control.runtime_readiness_authority import build_runtime_readiness_authority


def build_runtime_status_unification(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    readiness = build_runtime_readiness_authority(truth)["runtime_readiness_authority"]
    authority = build_runtime_operational_authority(truth)
    hydration = truth.get("hydration_progress") or {}
    supervision = truth.get("runtime_process_supervision") or {}
    recovery = truth.get("runtime_recovery_finalization") or truth.get("operational_recovery_state") or {}
    calmness = truth.get("runtime_calmness_lock") or {}
    return {
        "runtime_status_unification": {
            "readiness_state": readiness.get("state"),
            "readiness_score": readiness.get("score"),
            "hydration": {
                "partial": bool(hydration.get("partial")),
                "tier": hydration.get("tier") or hydration.get("max_tier"),
                "tiers_complete": list(hydration.get("tiers_complete") or [])[:6],
            },
            "supervision": {
                "verified": bool(truth.get("runtime_supervision_verified")),
                "conflicts": len(supervision.get("conflicts") or []),
            },
            "provider_health": (truth.get("routing_summary") or {}).get("primary_provider"),
            "recovery_active": readiness.get("state") == "recovering",
            "ownership": (truth.get("runtime_ownership") or {}).get("held"),
            "operational_pressure": (truth.get("runtime_operational_pressure") or {}).get("level"),
            "throttling": (truth.get("operational_throttling") or {}).get("throttled"),
            "degraded_mode": authority["operational_authority"].get("degraded_mode"),
            "calmness_locked": calmness.get("locked"),
            "enterprise_ready": readiness.get("enterprise_ready"),
            "operator_message": authority["operational_authority"].get("operator_message"),
            "phase": "phase4_step22",
            "bounded": True,
        }
    }


def build_unified_runtime_status(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    """Alias for API ``GET /runtime/status``."""
    out = build_runtime_status_unification(truth)
    return {"runtime_status": out["runtime_status_unification"]}


def build_runtime_health_summary(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    unified = build_runtime_status_unification(truth)["runtime_status_unification"]
    readiness = (truth or {}).get("runtime_readiness_authority") or {}
    return {
        "runtime_health_summary": {
            "state": unified.get("readiness_state"),
            "score": unified.get("readiness_score"),
            "enterprise_ready": unified.get("enterprise_ready"),
            "degraded_mode": unified.get("degraded_mode"),
            "safe_for_operator": readiness.get("safe_for_operator"),
            "operator_message": unified.get("operator_message"),
            "phase": "phase4_step22",
            "bounded": True,
        }
    }
