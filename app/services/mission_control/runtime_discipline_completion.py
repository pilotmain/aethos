# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime discipline completion metrics (Phase 3 Step 16)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_metrics_discipline import get_runtime_discipline_metrics
from app.services.mission_control.runtime_cleanup_completion import build_cleanup_completion


def build_runtime_discipline_completion(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    disc = get_runtime_discipline_metrics()
    payload = truth.get("payload_discipline") if truth else {}
    cleanup = build_cleanup_completion()
    return {
        "duplicated_sections_prevented": int(disc.get("operational_duplication_prevented") or 0),
        "payload_reduction_effective": bool((payload or {}).get("payload_reduction_rate")),
        "timeline_collapse_effective": disc.get("last_event_collapse_rate") is not None,
        "recommendation_dedup": True,
        "operational_signal_quality": _signal_quality(truth),
        "simplification_progress": cleanup.get("cleanup_completion_percentage"),
        "completion_locked": float(cleanup.get("cleanup_completion_percentage") or 0) >= 0.95,
    }


def build_simplification_progress() -> dict[str, Any]:
    c = build_cleanup_completion()
    return {
        "percentage": c.get("cleanup_completion_percentage"),
        "remaining": c.get("cleanup_remaining_surface_area"),
        "locked": c.get("locked"),
    }


def build_operational_signal_health(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    events = len(truth.get("runtime_events") or [])
    esc = int((truth.get("runtime_escalations") or {}).get("escalation_count") or 0)
    recs = len(((truth.get("runtime_recommendations") or {}).get("recommendations") or []))
    noise = esc + max(0, events - 24) + max(0, recs - 8)
    quality = max(0.0, 1.0 - noise * 0.03)
    return {
        "signal_quality_score": round(quality, 3),
        "event_count": events,
        "escalation_count": esc,
        "recommendation_count": recs,
        "healthy": quality >= 0.7,
    }


def _signal_quality(truth: dict[str, Any] | None) -> float:
    return float(build_operational_signal_health(truth).get("signal_quality_score") or 0.7)
