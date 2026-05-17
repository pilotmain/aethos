# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime stability coordination across subsystems (Phase 4 Step 24)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_operational_state_machine import build_runtime_operational_state_machine


def build_runtime_stability_coordinator(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    state = build_runtime_operational_state_machine(truth)["runtime_operational_state"]["state"]
    partial = bool((truth.get("hydration_progress") or {}).get("partial"))
    oscillation_risk = state in ("recovering", "degraded", "partially_degraded") and partial
    score = float(truth.get("runtime_readiness_score") or 0.85)
    if oscillation_risk:
        score = max(0.5, score - 0.1)
    if state == "operational" and not partial:
        score = min(1.0, score + 0.02)
    stable = score >= 0.75 and state not in ("critical", "offline")
    return {
        "runtime_stability": {
            "stable": stable,
            "calm_under_pressure": True,
            "avoid_state_oscillation": not oscillation_risk,
            "avoid_readiness_flips": True,
            "operational_consistency": stable,
            "phase": "phase4_step24",
            "bounded": True,
        },
        "runtime_stability_score": round(score, 3),
        "runtime_stability_history": list((truth.get("runtime_transition_history") or []))[-8:],
        "runtime_operational_stability": {"state": state, "stable": stable, "bounded": True},
        "runtime_long_session_health": {
            "healthy": stable,
            "extended_operation": True,
            "bounded": True,
        },
    }
