# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Default fields on planning rows (no planner_runtime import — avoids circular imports)."""

from __future__ import annotations

from typing import Any


def ensure_adaptive_planning_fields(row: dict[str, Any]) -> None:
    row.setdefault("planning_reasoning", [])
    row.setdefault("adaptive_changes", [])
    row.setdefault("retry_strategy_history", [])
    row.setdefault("delegation_decisions", [])
    row.setdefault("execution_quality", {"attempts": 0, "successes": 0, "failures": 0})
    for k in ("planning_reasoning", "adaptive_changes", "retry_strategy_history", "delegation_decisions"):
        if not isinstance(row.get(k), list):
            row[k] = []
    eq = row.get("execution_quality")
    if not isinstance(eq, dict):
        row["execution_quality"] = {"attempts": 0, "successes": 0, "failures": 0}
    else:
        eq.setdefault("attempts", 0)
        eq.setdefault("successes", 0)
        eq.setdefault("failures", 0)
