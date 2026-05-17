# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Formal runtime operational state machine (Phase 4 Step 23)."""

from __future__ import annotations

from typing import Any

OPERATIONAL_STATES = (
    "booting",
    "warming",
    "operational",
    "partially_degraded",
    "degraded",
    "recovering",
    "maintenance",
    "locked",
    "critical",
    "offline",
)


def _derive_state(truth: dict[str, Any]) -> str:
    readiness = (truth.get("runtime_readiness_authority") or {}).get("state")
    if readiness == "critical":
        return "critical"
    if readiness == "maintenance":
        return "maintenance"
    if readiness == "recovering":
        return "recovering"
    if (truth.get("runtime_ownership") or {}).get("conflict"):
        return "locked"
    partial = bool((truth.get("hydration_progress") or {}).get("partial"))
    resilience = (truth.get("runtime_resilience") or {}).get("status") or "healthy"
    if resilience == "offline" or truth.get("runtime_offline"):
        return "offline"
    if partial and readiness in ("warming", "partially_ready", "initializing"):
        return "warming"
    if readiness == "degraded" or resilience == "degraded":
        return "degraded"
    if partial or readiness == "partially_ready":
        return "partially_degraded"
    if readiness in ("initializing",):
        return "booting"
    return "operational"


def build_runtime_operational_state_machine(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    state = _derive_state(truth)
    prior = (truth.get("runtime_operational_state") or {}).get("state")
    history = list((truth.get("runtime_transition_history") or []))[-12:]
    if prior and prior != state:
        history.append({"from": prior, "to": state, "explainable": True, "logged": True})
    return {
        "runtime_operational_state": {
            "state": state,
            "mode": state,
            "operator_visible": True,
            "deterministic": True,
            "bounded": True,
        },
        "runtime_operational_mode": state,
        "runtime_state_transitions": {
            "allowed": list(OPERATIONAL_STATES),
            "current": state,
            "previous": prior,
        },
        "runtime_transition_history": history[-16:],
        "phase": "phase4_step23",
        "bounded": True,
    }
