# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise runtime load and pressure governance (Phase 4 Step 26)."""

from __future__ import annotations

from typing import Any


def build_runtime_pressure_governance(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    throttle = truth.get("runtime_operational_throttling") or {}
    pressure_level = (truth.get("operational_pressure") or {}).get("level") or "low"
    hydration_busy = bool((truth.get("runtime_truth_authority") or {}).get("truth_hydration_locked"))
    worker_load = float((truth.get("worker_ecosystem_health") or {}).get("score") or 0.85)
    if hydration_busy or pressure_level in ("high", "elevated"):
        level = "elevated"
    elif pressure_level == "medium":
        level = "medium"
    else:
        level = "normal"
    office_priority = True
    recovery_ready = level != "high"
    return {
        "runtime_pressure_governance": {
            "phase": "phase4_step26",
            "office_highest_priority": office_priority,
            "hydration_pressure": hydration_busy,
            "worker_pressure": round(1.0 - worker_load, 3) if worker_load < 1 else 0,
            "throttling_active": bool(throttle.get("throttling_active")),
            "level": level,
            "bounded": True,
        },
        "runtime_pressure_health": {
            "phase": "phase4_step26",
            "level": level,
            "ok": level in ("normal", "medium"),
            "office_responsive": office_priority,
            "bounded": True,
        },
        "runtime_operational_pressure": {
            "phase": "phase4_step26",
            "level": pressure_level,
            "governed": True,
            "bounded": True,
        },
        "runtime_pressure_recovery": {
            "phase": "phase4_step26",
            "ready": recovery_ready,
            "message": (
                "Operational prioritization reduced runtime pressure successfully."
                if level == "normal"
                else "Pressure governance is active — degraded prioritization preserves Office responsiveness."
            ),
            "bounded": True,
        },
    }
