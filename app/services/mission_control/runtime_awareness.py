# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise runtime awareness (Phase 4 Step 5)."""

from __future__ import annotations

from typing import Any


def build_operational_stability_matrix(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    calm = (truth.get("runtime_calmness") or {}).get("calm_score", 0.75)
    trust = float(truth.get("operational_trust_score") or 0.8)
    pressure = (truth.get("operational_pressure") or {}).get("level", "low")
    return {
        "calmness": calm,
        "trust": trust,
        "pressure": pressure,
        "stable": pressure != "high" and calm >= 0.7,
    }


def build_runtime_pressure_awareness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return (truth or {}).get("operational_pressure") or {"level": "low"}


def build_governance_posture(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "readiness": (truth or {}).get("governance_readiness"),
        "searchable": (truth.get("governance_experience") or {}).get("searchable"),
        "escalations": (truth.get("runtime_escalations") or {}).get("escalation_count", 0),
    }


def build_enterprise_operational_posture_awareness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "readiness_score": truth.get("runtime_readiness_score"),
        "maturity": (truth.get("enterprise_operational_posture") or {}).get("overall_posture"),
        "risk_posture": (truth.get("runtime_risk_projection") or {}).get("deployment_risk_growth"),
        "scalability_posture": (truth.get("runtime_scalability_health") or {}).get("status"),
    }


def build_runtime_awareness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "operational_stability_matrix": build_operational_stability_matrix(truth),
        "runtime_pressure_awareness": build_runtime_pressure_awareness(truth),
        "governance_posture": build_governance_posture(truth),
        "enterprise_operational_posture": build_enterprise_operational_posture_awareness(truth),
        "worker_health": (truth.get("worker_ecosystem_health") or {}).get("status"),
        "queue_health": "nominal",
    }
