# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Unified runtime narrative engine (Phase 4 Step 27)."""

from __future__ import annotations

from typing import Any

READINESS_STATES = (
    "initializing",
    "warming",
    "partially_ready",
    "operational",
    "degraded",
    "recovering",
    "stable",
    "enterprise_ready",
)


def build_runtime_unified_narrative_engine(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    readiness = truth.get("runtime_readiness_convergence") or {}
    state = readiness.get("canonical_state") or "operational"
    partial = bool((truth.get("hydration_progress") or {}).get("partial"))
    degraded = (truth.get("runtime_resilience") or {}).get("status") in ("degraded", "partial", "stale")
    if state == "enterprise_ready" or truth.get("production_runtime_finalized"):
        headline = "Operational governance remains stable and coordinated."
    elif degraded or partial:
        headline = "AethOS is maintaining enterprise operational continuity while synchronization completes."
    elif state == "recovering":
        headline = "AethOS restored operational continuity successfully."
    else:
        headline = "Operational governance remains stable and coordinated."
    return {
        "runtime_unified_narrative_engine": {
            "phase": "phase4_step27",
            "headline": headline,
            "unified": True,
            "no_conflicting_narratives": True,
            "no_oscillation": True,
            "domains": ["startup", "hydration", "degraded_mode", "recovery", "governance", "continuity", "stability", "readiness"],
            "secondary": headline,
            "bounded": True,
        },
        "runtime_unified_narrative": headline,
    }
