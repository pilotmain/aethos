# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Unified runtime narrative model for Mission Control (Phase 4 Step 21)."""

from __future__ import annotations

from typing import Any

NARRATIVE_ROLES: dict[str, str] = {
    "office": "Operational command center",
    "runtime_overview": "Runtime readiness and operational health",
    "runtime_intelligence": "Recommendations, routing, forecasts, and advisories",
    "runtime_supervision": "Processes, locks, startup, and ownership",
    "governance": "Operational accountability and history",
    "executive_overview": "Enterprise posture and readiness",
    "runtime_recovery": "Hydration recovery and degraded-mode guidance",
}

REMOVE_DUPLICATES = (
    "duplicate readiness banners across office and runtime-overview",
    "repeated trust score headlines",
    "overlapping recovery panels on overview and recovery routes",
)


def build_runtime_narrative_unification(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    startup = (truth.get("runtime_startup_experience") or {}).get("enterprise_stage") or {}
    return {
        "runtime_narrative_unification": {
            "coherent_operational_narrative": True,
            "roles": NARRATIVE_ROLES,
            "remove_duplicates": list(REMOVE_DUPLICATES),
            "primary_headline_by_surface": {
                "office": "Operational command center",
                "runtime": "Runtime readiness and operational health",
            },
            "current_enterprise_stage": startup,
            "phase": "phase4_step21",
            "bounded": True,
        }
    }
