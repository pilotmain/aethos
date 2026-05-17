# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise responsiveness guarantees during hydration (Phase 4 Step 24)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_operational_throttling import build_runtime_operational_throttling


def build_runtime_responsiveness_guarantees(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    throttle = build_runtime_operational_throttling(truth).get("operational_throttling") or {}
    partial = bool((truth.get("hydration_progress") or {}).get("partial"))
    priorities = ["office", "runtime_overview", "runtime_supervision", "recovery", "governance"]
    if not partial:
        priorities.extend(["runtime_intelligence", "marketplace", "providers"])
    responsive = not throttle.get("truth_rebuild_blocked")
    return {
        "runtime_responsiveness_guarantees": {
            "responsive_during_hydration": responsive,
            "office_responsive": True,
            "avoid_blocking_rebuilds": True,
            "graceful_degradation": partial,
            "phase": "phase4_step24",
            "bounded": True,
        },
        "operational_surface_priorities": priorities,
        "runtime_responsiveness_health": {
            "healthy": responsive,
            "office_interval_ms": throttle.get("office_interval_ms"),
            "bounded": True,
        },
        "enterprise_responsiveness_certification": {
            "certified": responsive and not partial,
            "partial_acceptable": partial,
            "bounded": True,
        },
    }
