# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator continuity confidence reinforcement (Phase 4 Step 24)."""

from __future__ import annotations

from typing import Any


def build_runtime_operator_continuity_confidence(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    continuity = truth.get("runtime_continuity_certification") or {}
    recovery = truth.get("runtime_recovery_integrity") or {}
    readiness = truth.get("runtime_readiness_authority") or {}
    certified = bool(continuity.get("certified"))
    action_needed = bool(recovery.get("operator_action_required"))
    summary = (
        "Runtime continuity is fully preserved."
        if certified and not action_needed
        else "AethOS is stabilizing continuity — review recovery guidance if needed."
    )
    action_line = "No operator action is required." if not action_needed else "Operator review recommended."
    return {
        "runtime_operator_continuity_confidence": {
            "continuity_status": "preserved" if certified else "stabilizing",
            "recovery_integrity": recovery.get("stable", True),
            "operational_readiness": readiness.get("state"),
            "persistence_health": (truth.get("runtime_persistence_health") or {}).get("database_ok", True),
            "restart_safe": True,
            "enterprise_confidence": truth.get("runtime_operator_trust", {}).get("trusted"),
            "summary": summary,
            "operator_action": action_line,
            "phase": "phase4_step24",
            "bounded": True,
        }
    }
