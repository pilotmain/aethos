# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise operational discipline under pressure (Phase 4 Step 14)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_scalability import build_operational_pressure


def build_enterprise_operational_discipline(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    pressure = truth.get("operational_pressure") or build_operational_pressure(truth)
    throttle = truth.get("runtime_operational_throttling") or {}
    deferred = int((throttle.get("deferred_slices") or 0) if isinstance(throttle, dict) else 0)
    level = str(pressure.get("level") or "low")
    continuity = (truth.get("operational_continuity_engine") or {}).get("continuity_recovery_quality") or 0.85
    recovery_ok = (truth.get("runtime_resilience") or {}).get("status") in ("healthy", "recovering", None)
    prioritization = 0.9 if level == "low" else (0.75 if level == "medium" else 0.6)
    return {
        "enterprise_operational_discipline": {
            "operational_pressure_level": level,
            "runtime_prioritization_effectiveness": round(prioritization, 3),
            "deferred_workload_count": deferred,
            "continuity_preservation_score": round(float(continuity) if isinstance(continuity, (int, float)) else 0.85, 3),
            "recovery_success_score": 1.0 if recovery_ok else 0.7,
            "calmness_first": True,
            "office_responsiveness_preserved": not throttle.get("active") or level != "high",
            "bounded": True,
        }
    }
