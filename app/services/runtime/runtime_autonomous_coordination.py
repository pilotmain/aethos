# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Autonomous runtime operational coordination — not agent execution (Phase 4 Step 26)."""

from __future__ import annotations

from typing import Any

from app.services.runtime.runtime_governance_authority import build_runtime_governance_authority
from app.services.runtime.runtime_recovery_authority import build_runtime_recovery_authority


def build_runtime_autonomous_coordination(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    gov = build_runtime_governance_authority(truth)
    recovery = build_runtime_recovery_authority(truth)
    ownership_conflicts = len((truth.get("runtime_process_conflicts") or {}).get("items") or [])
    conflicts = int((recovery.get("runtime_recovery_integrity") or {}).get("conflict_count") or ownership_conflicts)
    pressure = (truth.get("runtime_pressure_health") or {}).get("level") or "normal"
    stabilized = conflicts == 0 and gov.get("runtime_governance_authority", {}).get("authoritative")
    actions: list[str] = []
    if conflicts:
        actions.append("coordinate_process_recovery")
    if pressure in ("elevated", "high"):
        actions.append("operational_throttling")
        actions.append("office_priority_preservation")
    if truth.get("runtime_resilience", {}).get("status") in ("degraded", "partial"):
        actions.append("degraded_mode_stabilization")
    if not actions:
        actions.append("continuity_preservation")
    return {
        "runtime_autonomous_coordination": {
            "phase": "phase4_step26",
            "coordination_active": True,
            "hidden_operator_actions": False,
            "runtime_operational_coordination_only": True,
            "actions": actions,
            "stabilized": stabilized,
            "operator_message": (
                "AethOS coordinated runtime recovery automatically while preserving operational continuity."
                if stabilized
                else "Operational prioritization is reducing runtime pressure — Office remains authoritative."
            ),
            "pressure_message": (
                "Operational prioritization reduced runtime pressure successfully."
                if pressure == "normal"
                else "Runtime pressure governance is active — Office has highest priority."
            ),
            "bounded": True,
        }
    }
