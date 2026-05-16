# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime strategic planning (Phase 4 Step 5)."""

from __future__ import annotations

from typing import Any


def build_operational_trajectory_intelligence(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    traj = (truth or {}).get("runtime_trajectory") or (truth or {}).get("operational_trajectory_summary") or {}
    return {"direction": traj.get("direction"), "summary": traj.get("summary"), "advisory": True}


def build_enterprise_scalability_projection(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return (truth or {}).get("scalability_forecasts") or (truth or {}).get("strategic_ecosystem_projection") or {}


def build_strategic_operational_forecasts(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return (truth or {}).get("adaptive_operational_forecasting") or (truth or {}).get("operational_forecasts") or {}


def build_continuity_health_projection(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    c = (truth or {}).get("continuity_memory") or {}
    return {"healthy": bool(c), "projection": "stable", "advisory": True}


def build_strategic_runtime_planning(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "operational_trajectory_intelligence": build_operational_trajectory_intelligence(truth),
        "enterprise_scalability_projection": build_enterprise_scalability_projection(truth),
        "strategic_operational_forecasts": build_strategic_operational_forecasts(truth),
        "continuity_health_projection": build_continuity_health_projection(truth),
        "strategic_warnings": (truth or {}).get("strategic_runtime_alerts") or [],
        "advisory_only": True,
    }
