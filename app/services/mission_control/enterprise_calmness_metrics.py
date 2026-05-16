# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise calmness metrics — launch lock (Phase 4 Step 13)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.operational_calmness import build_runtime_calmness
from app.services.mission_control.operational_calmness_lock import build_calmness_lock
from app.services.mission_control.runtime_calmness_integrity import build_runtime_calmness_integrity


def build_runtime_calmness_metrics(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    calm = build_runtime_calmness(truth)
    lock = build_calmness_lock(truth)
    integrity = build_runtime_calmness_integrity(truth)
    noise = float(lock.get("operational_noise_reduction") or 0.5)
    return {
        "calmness_score": calm.get("calm_score"),
        "operational_clarity_score": calm.get("quality_score") or integrity.get("event_signal_quality"),
        "noise_reduction_ratio": noise,
        "signal_prioritization_effectiveness": round(min(1.0, noise + 0.15), 3),
        "feels_calm": calm.get("feels_calm"),
        "under_pressure": (truth.get("operational_pressure") or {}).get("level") not in (None, "low"),
        "bounded": True,
    }


def build_runtime_signal_health(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    integrity = build_runtime_calmness_integrity(truth)
    return {
        "event_signal_quality": integrity.get("event_signal_quality"),
        "escalation_visibility_score": integrity.get("escalation_visibility_score"),
        "operational_noise_score": integrity.get("operational_noise_score"),
        "signal_over_noise": integrity.get("calmness_integrity", {}).get("signal_over_noise"),
        "bounded": True,
    }
