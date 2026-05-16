# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Strategic runtime awareness and trends (Phase 4 Step 1)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state


def build_strategic_runtime_alerts(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    truth = truth or {}
    alerts: list[dict[str, Any]] = []
    esc = int((truth.get("runtime_escalations") or {}).get("escalation_count") or 0)
    if esc > 3:
        alerts.append({"kind": "governance_escalation_frequency", "severity": "medium", "count": esc})
    pressure = truth.get("operational_pressure") or {}
    if pressure.get("level") == "high":
        alerts.append({"kind": "runtime_pressure_growth", "severity": "high"})
    if not (truth.get("payload_discipline") or {}).get("within_budget"):
        alerts.append({"kind": "enterprise_operational_degradation", "severity": "medium", "area": "payload"})
    st = load_runtime_state()
    repairs = (st.get("repair_contexts") or {}).get("latest_by_project") or {}
    if isinstance(repairs, dict) and len(repairs) > 4:
        alerts.append({"kind": "recurring_repair_loops", "severity": "warning", "count": len(repairs)})
    return alerts[:8]


def build_operational_trajectory_summary(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    readiness = float(truth.get("runtime_readiness_score") or 0.75)
    trust = float(truth.get("operational_trust_score") or 0.75)
    return {
        "direction": "stable" if readiness >= 0.75 and trust >= 0.75 else "attention",
        "readiness_score": readiness,
        "trust_score": trust,
        "summary": "Operational trajectory stable — continue advisory monitoring."
        if readiness >= 0.75
        else "Trajectory needs operator review — check escalations and pressure.",
    }


def build_enterprise_operational_trends(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "trust_trend": (truth.get("adaptive_operational_learning") or {}).get("trust_trend", "stable"),
        "pressure_level": (truth.get("operational_pressure") or {}).get("level"),
        "hydration_ms": (truth.get("runtime_performance") or {}).get("hydration_latency_ms"),
        "worker_count": ((truth.get("runtime_workers") or {}).get("active_count")),
    }


def build_runtime_maturity_summary(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    score = float(truth.get("runtime_readiness_score") or 0.75)
    return {
        "maturity_level": "enterprise" if score >= 0.85 else ("maturing" if score >= 0.7 else "developing"),
        "readiness_score": score,
        "phase": "phase4_step1",
    }


def build_runtime_strategy_awareness(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "strategic_runtime_alerts": build_strategic_runtime_alerts(truth),
        "operational_trajectory_summary": build_operational_trajectory_summary(truth),
        "enterprise_operational_trends": build_enterprise_operational_trends(truth),
        "runtime_maturity_summary": build_runtime_maturity_summary(truth),
    }
