# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Strategic forecast optimization (Phase 4 Step 3)."""

from __future__ import annotations

from typing import Any


def build_strategic_runtime_projection(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    traj = (truth or {}).get("runtime_trajectory") or {}
    risk = (truth or {}).get("runtime_risk_projection") or {}
    return {
        "trajectory": traj.get("direction", "stable"),
        "deployment_risk": risk.get("deployment_risk_growth", "low"),
        "horizon": "short_term",
        "advisory": True,
    }


def build_enterprise_operational_forecast_quality(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    forecasting = (truth or {}).get("operational_forecasting") or {}
    return {
        "quality_score": 0.88 if forecasting.get("advisory") else 0.7,
        "runtime_derived": forecasting.get("runtime_derived", True),
        "bounded": True,
    }


def build_runtime_prediction_confidence(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    trust = float((truth or {}).get("operational_trust_score") or 0.8)
    readiness = float((truth or {}).get("runtime_readiness_score") or 0.75)
    conf = round(min(1.0, (trust + readiness) / 2), 3)
    return {"confidence": conf, "level": "high" if conf >= 0.8 else "medium", "advisory": True}


def build_adaptive_operational_forecasting(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "strategic_runtime_projection": build_strategic_runtime_projection(truth),
        "enterprise_operational_forecast_quality": build_enterprise_operational_forecast_quality(truth),
        "runtime_prediction_confidence": build_runtime_prediction_confidence(truth),
        "forecasts": (truth or {}).get("operational_forecasts"),
        "advisory": True,
    }
