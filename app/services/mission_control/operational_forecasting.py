# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise operational forecasting — advisory, bounded (Phase 4 Step 2)."""

from __future__ import annotations

from typing import Any


def build_runtime_risk_projection(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    pressure = truth.get("operational_pressure") or {}
    esc = int((truth.get("runtime_escalations") or {}).get("escalation_count") or 0)
    return {
        "deployment_risk_growth": "low" if pressure.get("level") != "high" else "medium",
        "governance_escalation_likelihood": "medium" if esc > 2 else "low",
        "repair_failure_probability": "low",
        "advisory": True,
        "bounded": True,
    }


def build_scalability_forecasts(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    scale = (truth or {}).get("runtime_scalability_health") or {}
    return {
        "pressure_growth": scale.get("status", "healthy"),
        "event_buffer_size": scale.get("event_buffer_size"),
        "slice_cache_hit_rate": scale.get("slice_cache_hit_rate"),
        "forecast": "stable" if scale.get("status") == "healthy" else "review_capacity",
    }


def build_enterprise_operational_outlook(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    traj = (truth or {}).get("operational_trajectory_summary") or {}
    return {
        "outlook": traj.get("direction", "stable"),
        "summary": traj.get("summary", "Enterprise operational outlook stable."),
        "horizon": "short_term",
        "governance_visible": True,
    }


def build_operational_forecasting(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "advisory": True,
        "explainable": True,
        "runtime_derived": True,
        "risk_projection": build_runtime_risk_projection(truth),
        "scalability": build_scalability_forecasts(truth),
        "outlook": build_enterprise_operational_outlook(truth),
    }
