# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Office operational stream discipline — calm staggered refresh (Phase 4 Step 7)."""

from __future__ import annotations

from typing import Any


def build_office_operational_stream(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    pressure = truth.get("operational_pressure") or {}
    throttling = truth.get("runtime_operational_throttling") or {}
    partial = bool((truth.get("hydration_progress") or {}).get("partial"))
    return {
        "staggered_refresh_ms": {
            "orchestrator": 0,
            "workers": 400,
            "routing": 800,
            "events": 1200,
            "confidence": 1600,
        },
        "refresh_priority": ["orchestrator", "workers", "routing", "events", "confidence"],
        "silent_background_refresh": True,
        "cached_render_reuse": True,
        "calm_transitions": True,
        "stable_panel_refresh": True,
        "no_stacked_banners": True,
        "authoritative_entrypoint": True,
        "calmness_preserved": pressure.get("level") != "high",
        "office_interval_ms": throttling.get("office_interval_ms") or 12000,
        "advisory_deferred": throttling.get("advisory_deferred", False),
        "progressive_hydration": partial,
        "runtime_confidence_calm": (truth.get("operator_confidence") or {}).get("summary"),
        "phase": "phase4_step24",
        "bounded": True,
    }
