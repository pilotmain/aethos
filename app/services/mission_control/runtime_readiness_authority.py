# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Authoritative runtime readiness evaluation (Phase 4 Step 22)."""

from __future__ import annotations

from typing import Any

READINESS_STATES = (
    "initializing",
    "warming",
    "partially_ready",
    "operational",
    "degraded",
    "recovering",
    "maintenance",
    "critical",
)


def build_runtime_readiness_authority(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    score = float(truth.get("runtime_readiness_score") or 0.0)
    hydration = truth.get("hydration_progress") or {}
    resilience = (truth.get("runtime_resilience") or {}).get("status") or "healthy"
    partial = bool(hydration.get("partial"))
    ownership = truth.get("runtime_ownership") or {}
    db = truth.get("runtime_db_health") or {}
    supervision = truth.get("runtime_process_supervision") or {}
    degraded_components: list[str] = []
    warming_components: list[str] = []

    if partial:
        warming_components.append("hydration")
    if resilience in ("degraded", "partial", "stale"):
        degraded_components.append("runtime_resilience")
    if ownership.get("conflict"):
        degraded_components.append("runtime_ownership")
    if db.get("locked") or db.get("status") == "locked":
        degraded_components.append("database")
    if supervision.get("conflicts"):
        degraded_components.append("process_supervision")

    if score < 0.4 or resilience == "critical":
        state = "critical"
    elif ownership.get("recovering") or resilience == "recovering":
        state = "recovering"
    elif truth.get("maintenance_mode"):
        state = "maintenance"
    elif degraded_components:
        state = "degraded"
    elif partial or score < 0.78:
        state = "partially_ready" if score >= 0.5 else "warming"
    elif score < 0.55:
        state = "warming"
    elif hydration.get("tier") == "initializing":
        state = "initializing"
    else:
        state = "operational"

    enterprise_ready = state in ("operational", "partially_ready") and score >= 0.78
    safe = state not in ("critical", "maintenance") and score >= 0.5

    return {
        "runtime_readiness_authority": {
            "state": state,
            "score": round(score, 3),
            "enterprise_ready": enterprise_ready,
            "safe_for_operator": safe,
            "degraded_components": degraded_components,
            "warming_components": warming_components,
            "authoritative": True,
            "phase": "phase4_step22",
            "bounded": True,
        }
    }
