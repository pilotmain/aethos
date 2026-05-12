# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Mission Control execution truth labels — loop completion ≠ verified external execution (P0).
"""

from __future__ import annotations

from typing import Any

from app.services.mission_execution_truth import agent_output_is_unverified_stub


def task_execution_verified(task_output: Any) -> bool:
    return not agent_output_is_unverified_stub(task_output)


def derive_task_execution_state(task: dict[str, Any]) -> str:
    """Per-task execution truth for Mission Control (merged mission flags when present)."""
    if task.get("requires_access"):
        return "access_required"
    st = str(task.get("status") or "").lower()
    if st not in ("completed",):
        return "unknown"
    if task.get("execution_verified"):
        return "verified"
    if task.get("is_external_execution"):
        return "diagnostic_only"
    return "completed_unverified"


def derive_mission_execution_state(mission: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
    if mission.get("requires_access"):
        return "access_required"
    st = str(mission.get("status") or "").lower()
    if st in ("running", "queued"):
        return "unknown"
    if st == "timeout":
        return "completed_unverified"
    if st != "completed":
        return "not_executed"
    if not tasks:
        return "completed_unverified"
    if mission.get("execution_verified"):
        return "verified"
    if mission.get("is_external_execution"):
        return "diagnostic_only"
    return "completed_unverified"


__all__ = [
    "derive_mission_execution_state",
    "derive_task_execution_state",
    "task_execution_verified",
]
