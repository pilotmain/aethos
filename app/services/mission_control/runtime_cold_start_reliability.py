# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Cold hydration reliability and operator-visible progress (Phase 4 Step 22)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_cold_start_lock import build_runtime_cold_start, build_runtime_readiness_progress
from app.services.mission_control.runtime_hydration_diagnostics import build_runtime_hydration_diagnostics


STALL_THRESHOLD_MS = 45_000


def build_runtime_cold_start_reliability(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    cold = build_runtime_cold_start(truth).get("runtime_cold_start") or {}
    progress = build_runtime_readiness_progress(truth).get("readiness_progress") or {}
    diag = build_runtime_hydration_diagnostics(truth).get("runtime_hydration_diagnostics") or {}
    duration = float(diag.get("cold_start_duration_ms") or cold.get("cold_hydration_duration_ms") or 0)
    partial = bool(progress.get("partial"))
    stalled = partial and duration > STALL_THRESHOLD_MS
    operator_message = (
        "AethOS is still preparing enterprise runtime intelligence. "
        "Core systems are available while advanced operational analysis finishes loading."
        if partial
        else "AethOS runtime intelligence is fully available."
    )
    return {
        "cold_start_reliability": {
            "progressive": True,
            "recoverable": True,
            "trustworthy": not stalled,
            "stalled_stage_detected": stalled,
            "retry_count": int((truth.get("hydration_progress") or {}).get("retry_count") or 0),
            "degraded_fallback_active": partial,
            "slice_availability": progress.get("percent_estimate"),
            "operator_visible_progress": progress.get("percent_estimate"),
            "operator_message": operator_message,
            "phase": "phase4_step22",
            "bounded": True,
        },
        "hydration_progress_visibility": {
            "partial": partial,
            "percent": progress.get("percent_estimate"),
            "tiers_complete": progress.get("tiers_complete"),
            "message": operator_message,
            "bounded": True,
        },
        "runtime_boot_integrity": {
            "cold_start_active": cold.get("cold_start_active"),
            "summary_first": cold.get("summary_first_rendering"),
            "feels_alive": progress.get("feels_alive"),
            "bounded": True,
        },
    }
