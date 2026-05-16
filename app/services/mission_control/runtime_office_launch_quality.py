# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Office launch-quality enrichment (Phase 4 Step 14)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_cold_start_lock import build_runtime_readiness_progress


def enrich_office_launch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    progress = build_runtime_readiness_progress(payload)
    readiness = progress["readiness_progress"]
    pct = readiness.get("percent_estimate", 1.0)
    partial = readiness.get("partial")
    summary = "Runtime operational"
    if partial and pct < 1.0:
        summary = f"Runtime warming up — {int(pct * 100)}% operational tiers ready"
    elif partial:
        summary = "Runtime warming up — summary-first command center active"
    return {
        **payload,
        "runtime_readiness_summary": summary,
        "office_launch_quality": {
            "launch_grade": True,
            "priorities_visible": [
                "health",
                "orchestrator",
                "active_work",
                "readiness",
                "routing",
                "workers",
            ],
            "calm_empty_states": True,
            "bounded": True,
        },
        **progress,
    }
