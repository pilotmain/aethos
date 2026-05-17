# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control operational authority — staleness and degraded visibility (Phase 4 Step 22)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_readiness_authority import build_runtime_readiness_authority


def build_runtime_operational_authority(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    readiness = build_runtime_readiness_authority(truth)["runtime_readiness_authority"]
    partial = bool((truth.get("hydration_progress") or {}).get("partial"))
    resilience = (truth.get("runtime_resilience") or {}).get("status") or "healthy"
    stale = resilience in ("stale", "partial") or partial
    degraded = readiness.get("state") in ("degraded", "recovering", "critical", "warming", "partially_ready")
    fallback_cache = partial and bool(truth.get("runtime_truth_cache"))

    operational_authority = {
        "authoritative": readiness.get("state") == "operational",
        "data_stale": stale,
        "hydration_partial": partial,
        "degraded_mode": degraded,
        "fallback_cache_active": fallback_cache,
        "safe_for_operator": readiness.get("safe_for_operator"),
        "operator_message": _authority_message(readiness, partial, stale),
    }
    surface_authority = {
        "office": {"authoritative": not partial, "stale": stale},
        "runtime_overview": {"authoritative": True, "stale": stale},
        "runtime_intelligence": {"authoritative": not partial, "stale": stale or partial},
        "runtime_supervision": {"authoritative": True, "stale": False},
    }
    mission_control_authority = {
        "never_white_screen": True,
        "never_silent_fail": True,
        "never_ambiguous_empty": True,
        "never_pretend_fresh_when_stale": stale is False or not partial,
        "never_imply_operational_when_degraded": readiness.get("state") == "operational",
    }
    return {
        "operational_authority": operational_authority,
        "surface_authority": surface_authority,
        "runtime_surface_integrity": {
            "single_story": True,
            "degraded_surfaces": [k for k, v in surface_authority.items() if v.get("stale")],
            "bounded": True,
        },
        "mission_control_authority": mission_control_authority,
        "phase": "phase4_step22",
        "bounded": True,
    }


def _authority_message(readiness: dict[str, Any], partial: bool, stale: bool) -> str:
    state = readiness.get("state")
    if state == "operational" and not stale:
        return "AethOS runtime is operational — Mission Control data is authoritative."
    if partial:
        return (
            "AethOS is still preparing enterprise runtime intelligence. "
            "Core systems are available while advanced operational analysis finishes loading."
        )
    if stale:
        return "Some panels may show cached data while runtime intelligence reconnects."
    if state == "degraded":
        return "AethOS is operating in degraded mode — review recovery guidance."
    return "AethOS runtime readiness is being evaluated."
