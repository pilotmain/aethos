# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime simplification lock — canonical systems and duplicate detection (Phase 4 Step 21)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_deprecation_registry import build_runtime_deprecation_registry
from app.services.mission_control.runtime_surface_consolidation import build_runtime_surface_consolidation


def build_runtime_simplification_lock(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    surfaces = build_runtime_surface_consolidation()["runtime_surface_consolidation"]
    deprecated = build_runtime_deprecation_registry()["runtime_deprecation_registry"]
    duplicate_surfaces = [
        "operational-insights vs runtime-intelligence",
        "runtime-overview vs runtime-readiness banners",
        "duplicate trust narratives on office + overview",
    ]
    return {
        "runtime_simplification_lock": {
            "locked": True,
            "canonical_systems": [
                "build_runtime_truth",
                "get_cached_runtime_truth",
                "runtime_ownership_lock",
                "runtime_startup_coordination",
                "production_cut_certification",
            ],
            "duplicate_surfaces": duplicate_surfaces,
            "deprecated_operational_paths": list(deprecated.get("deprecated_views", {}).keys())[:8],
            "unnecessary_parallel_systems": [],
            "simplification_opportunities": surfaces.get("avoid_duplicate_narratives") or [],
            "phase": "phase4_step21",
            "bounded": True,
        }
    }
