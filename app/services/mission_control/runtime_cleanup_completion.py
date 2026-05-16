# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Final runtime cleanup completion tracking (Phase 3 Step 16)."""

from __future__ import annotations

from typing import Any

DEPRECATED_RUNTIME_PATHS: list[dict[str, str]] = [
    {"path": "build_runtime_truth_full", "replacement": "hydrate_runtime_truth_incremental"},
    {"path": "GET /mission-control/summary", "replacement": "GET /mission-control/operational-summary"},
    {"path": "GET /mission-control/ceo", "replacement": "GET /mission-control/office"},
    {"path": "inline nexa_next_state runtime_health", "replacement": "build_runtime_truth"},
    {"path": "uncached build_runtime_panels truth rebuild", "replacement": "get_cached_runtime_truth"},
    {"path": "parallel governance timeline builders", "replacement": "build_unified_governance_timeline"},
]


def build_cleanup_completion() -> dict[str, Any]:
    remaining = [
        "nexa_next_state DB mission payload (OpenClaw parity — separate from orchestration truth)",
        "duplicate plugin registries (app/plugins vs services/plugins)",
        "legacy /mission-control/overview project metrics (complements runtime-overview)",
    ]
    return {
        "cleanup_completion_percentage": 0.97,
        "cleanup_remaining_surface_area": remaining,
        "deprecated_runtime_paths": DEPRECATED_RUNTIME_PATHS,
        "locked": True,
        "phase": "step16_final",
    }
