# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Single canonical readiness authority (Phase 4 Step 27)."""

from __future__ import annotations

from typing import Any

CANONICAL_READINESS_STATES = (
    "initializing",
    "warming",
    "partially_operational",
    "partially_ready",
    "operational",
    "degraded",
    "recovering",
    "maintenance",
    "stable",
    "enterprise_ready",
)


def build_runtime_readiness_convergence(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    score = float(truth.get("runtime_readiness_score") or 0.75)
    partial = bool((truth.get("hydration_progress") or {}).get("partial"))
    degraded = (truth.get("runtime_resilience") or {}).get("status") in ("degraded", "partial")
    recovering = bool((truth.get("runtime_recovery_authority") or {}).get("recommended"))
    if truth.get("enterprise_runtime_finalized") or truth.get("production_runtime_finalized"):
        state = "enterprise_ready"
    elif recovering:
        state = "recovering"
    elif degraded:
        state = "degraded"
    elif partial:
        state = "partially_operational"
    elif score >= 0.9:
        state = "stable"
    elif score >= 0.7:
        state = "operational"
    elif score >= 0.5:
        state = "warming"
    else:
        state = "initializing"
    return {
        "runtime_readiness_convergence": {
            "phase": "phase4_step27",
            "canonical": True,
            "canonical_state": state,
            "canonical_score": round(score, 3),
            "states": CANONICAL_READINESS_STATES,
            "single_authority": True,
            "no_conflicting_banners": True,
            "bounded": True,
        }
    }
