# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control runtime surface responsibilities (Phase 4 Step 20)."""

from __future__ import annotations

from typing import Any

SURFACE_RESPONSIBILITIES: dict[str, str] = {
    "office": "Operational command center",
    "runtime_overview": "Runtime health and readiness",
    "runtime_intelligence": "Recommendations, routing, and posture",
    "runtime_supervision": "Processes, locks, and startup coordination",
    "runtime_recovery": "Hydration recovery and degraded mode guidance",
    "governance": "Operational history and accountability",
    "executive_overview": "High-level enterprise posture",
    "operational_insights": "Consolidated into runtime intelligence (legacy route)",
    "runtime_story": "Operational narratives (secondary)",
    "explainability": "Decision explanations (secondary)",
}


def build_runtime_surface_consolidation() -> dict[str, Any]:
    return {
        "runtime_surface_consolidation": {
            "single_operational_story": True,
            "surfaces": SURFACE_RESPONSIBILITIES,
            "primary_nav": ["office", "runtime_overview", "governance"],
            "avoid_duplicate_narratives": [
                "Do not duplicate readiness banners on runtime-overview and office",
                "Use runtime-supervision for process conflicts, not runtime-overview",
            ],
            "authoritative_surfaces": ["office", "runtime_overview", "runtime_supervision", "governance"],
            "deprecated_surfaces": ["operational_insights"],
            "alias_surfaces": {"operational_insights": "runtime_intelligence"},
            "fallback_surfaces": ["runtime_story", "explainability"],
            "phase": "phase4_step22",
            "bounded": True,
        }
    }
