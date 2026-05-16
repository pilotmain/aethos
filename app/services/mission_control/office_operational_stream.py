# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Office operational stream discipline — calm staggered refresh (Phase 4 Step 7)."""

from __future__ import annotations

from typing import Any


def build_office_operational_stream(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    pressure = (truth or {}).get("operational_pressure") or {}
    throttling = (truth or {}).get("runtime_operational_throttling") or {}
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
        "calmness_preserved": not pressure.get("level") == "high",
        "office_interval_ms": throttling.get("office_interval_ms") or 12000,
        "advisory_deferred": throttling.get("advisory_deferred", False),
    }
