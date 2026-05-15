# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Coordination agent health vocabulary (OpenClaw reliability parity)."""

from __future__ import annotations

# Primary health axis for assignment / isolation decisions.
COORDINATION_HEALTH_STATUSES: frozenset[str] = frozenset(
    {
        "healthy",
        "degraded",
        "recovering",
        "overloaded",
        "offline",
        "failed",
    }
)

# Eligible for **new** assignments (healthy enough + not structurally isolated).
ASSIGNABLE_COORDINATION_HEALTH: frozenset[str] = frozenset({"healthy", "degraded"})

# Treat missing health as healthy (forward-compatible JSON).
DEFAULT_COORDINATION_HEALTH = "healthy"


def effective_coordination_health(row: dict) -> str:
    h = str(row.get("coordination_health") or "").strip().lower()
    if h in COORDINATION_HEALTH_STATUSES:
        return h
    # Backfill: idle workload implies healthy if no explicit health field.
    if str(row.get("status") or "").strip().lower() == "idle" and not row.get("coordination_health"):
        return "healthy"
    return DEFAULT_COORDINATION_HEALTH


def is_assignable_coordination_health(health: str) -> bool:
    return str(health or "").strip().lower() in ASSIGNABLE_COORDINATION_HEALTH
