# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operational performance completion metrics (Phase 3 Step 16)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_hydration import get_hydration_metrics


def build_operational_performance_completion(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    perf = truth.get("runtime_performance") or {}
    disc = truth.get("payload_discipline") or {}
    h = get_hydration_metrics()
    hydration_ms = float(perf.get("hydration_latency_ms") or h.get("last_hydration_ms") or 0)
    payload_bytes = int(disc.get("payload_bytes") or perf.get("payload_bytes") or 0)
    max_bytes = int(disc.get("payload_max_bytes") or 400_000)
    payload_eff = round(1.0 - payload_bytes / max(max_bytes, 1), 4)
    hydration_eff = 1.0 if hydration_ms < 2000 else (0.7 if hydration_ms < 5000 else 0.4)
    return {
        "runtime_payload_efficiency": payload_eff,
        "runtime_hydration_efficiency": round(hydration_eff, 3),
        "operational_latency_ms": hydration_ms,
        "timeline_responsiveness_ms": float(
            (truth.get("runtime_discipline") or {}).get("last_timeline_build_ms") or 0
        ),
        "mission_control_responsiveness": {
            "target_ms": 500,
            "last_hydration_ms": hydration_ms,
            "within_target": hydration_ms < 500,
        },
    }
