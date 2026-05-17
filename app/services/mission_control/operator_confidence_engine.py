# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator confidence summaries — calm operational assurance (Phase 4 Step 22)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_readiness_authority import build_runtime_readiness_authority
from app.services.mission_control.runtime_recovery_integrity import build_runtime_recovery_history


def build_operator_confidence(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    readiness = build_runtime_readiness_authority(truth)["runtime_readiness_authority"]
    hist = build_runtime_recovery_history(truth)["runtime_recovery_history"]
    partial = bool((truth.get("hydration_progress") or {}).get("partial"))
    state = readiness.get("state")
    summary = _confidence_summary(state, partial, hist)
    return {
        "operator_confidence": {
            "summary": summary,
            "confidence_level": readiness.get("score"),
            "safe_for_operator": readiness.get("safe_for_operator"),
            "phase": "phase4_step22",
            "bounded": True,
        },
        "runtime_operator_assurance": {
            "message": summary,
            "enterprise_ready": readiness.get("enterprise_ready"),
            "bounded": True,
        },
        "enterprise_runtime_assurance": {
            "operational": state == "operational",
            "recoverable": state in ("operational", "recovering", "partially_ready", "degraded"),
            "bounded": True,
        },
    }


def _confidence_summary(state: str, partial: bool, hist: dict[str, Any]) -> str:
    if state == "operational" and not partial:
        return "AethOS runtime is operational and healthy. All enterprise systems are synchronized."
    if hist.get("events") and state in ("operational", "recovering", "degraded"):
        return "AethOS recovered from a provider interruption. No operator action is currently required."
    if partial or state in ("warming", "partially_ready"):
        return (
            "Advanced intelligence systems are still warming, "
            "but core orchestration is fully available."
        )
    if state == "degraded":
        return "AethOS is operating in degraded mode — review recovery guidance when convenient."
    if state == "critical":
        return "AethOS needs operator attention — use recovery and supervision panels."
    return "AethOS runtime confidence is being established."
