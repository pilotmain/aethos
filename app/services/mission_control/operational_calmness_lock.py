# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operational calmness lock — stable noise reduction (Phase 3 Step 16)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.operational_calmness import build_runtime_calmness


def build_calmness_lock(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    calm = truth.get("runtime_calmness") or build_runtime_calmness(truth)
    disc = truth.get("runtime_discipline") or {}
    tl = truth.get("unified_operational_timeline") or {}
    raw = int(tl.get("deduped_from") or tl.get("entry_count") or 0)
    windowed = int(tl.get("entry_count") or 0)
    noise_reduction = round(1.0 - windowed / max(1, raw), 4) if raw else 1.0
    return {
        "calmness_stability": calm.get("calm_score"),
        "operational_noise_reduction": noise_reduction,
        "event_signal_quality": (truth.get("operational_signal_health") or {}).get("signal_quality_score"),
        "timeline_noise_reduction": noise_reduction,
        "locked": bool(calm.get("feels_calm")),
        "event_collapse_rate": disc.get("last_event_collapse_rate"),
        "prioritized_events": calm.get("prioritized_events") or [],
    }
