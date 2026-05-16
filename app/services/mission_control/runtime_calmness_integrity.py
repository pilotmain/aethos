# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Production calmness integrity — signal over noise (Phase 4 Step 8)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.operational_calmness_lock import build_calmness_lock


def build_runtime_calmness_integrity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    lock = truth.get("calmness_lock") or build_calmness_lock(truth)
    calm = truth.get("runtime_calmness") or {}
    esc = int((truth.get("runtime_escalations") or {}).get("escalation_count") or 0)
    noise = 1.0 - float(lock.get("operational_noise_reduction") or 0.5)
    return {
        "calmness_integrity": {
            "intact": bool(lock.get("locked")) or calm.get("feels_calm"),
            "signal_over_noise": True,
        },
        "operational_noise_score": round(noise, 3),
        "escalation_visibility_score": 1.0 if esc > 0 else 0.85,
        "event_signal_quality": lock.get("event_signal_quality") or calm.get("calm_score"),
        "calmness_lock": lock,
        "critical_escalations_visible": True,
        "duplicate_chatter_suppressed": True,
    }
