# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Autonomous operational recovery — advisory stabilization (Phase 4 Step 5)."""

from __future__ import annotations

from typing import Any


def build_degradation_signals(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    truth = truth or {}
    signals: list[dict[str, Any]] = []
    pressure = truth.get("operational_pressure") or {}
    if pressure.get("level") == "high":
        signals.append({"kind": "runtime_saturation", "severity": "high", "advisory": True})
    esc = int((truth.get("runtime_escalations") or {}).get("escalation_count") or 0)
    if esc > 2:
        signals.append({"kind": "escalation_risk", "count": esc, "advisory": True})
    if (truth.get("routing_summary") or {}).get("fallback_used"):
        signals.append({"kind": "unhealthy_routing_pattern", "advisory": True})
    repairs = (truth.get("runtime_escalations") or {}).get("active_escalations") or []
    if isinstance(repairs, list) and len(repairs) > 3:
        signals.append({"kind": "recurring_repair_loops", "count": len(repairs), "advisory": True})
    return signals[:10]


def build_runtime_stabilization(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    signals = build_degradation_signals(truth)
    return {
        "stable": len(signals) == 0,
        "recommendations": [
            "Review provider fallback chain." if any(s.get("kind") == "unhealthy_routing_pattern" for s in signals) else None,
            "Reduce worker concurrency temporarily." if any(s.get("kind") == "runtime_saturation" for s in signals) else None,
        ],
        "advisory_only": True,
    }


def build_recovery_coordination(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "orchestrator_owned": True,
        "actions": ["recommend_routing_change", "rebalance_pressure", "recommend_repair"],
        "approval_required": True,
    }


def build_runtime_resilience_engine(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    hard = (truth or {}).get("production_hardening") or {}
    return {"resilient": hard.get("resilient", True), "engine_mode": "advisory"}


def build_operational_recovery_state(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "degradation_signals": build_degradation_signals(truth),
        "runtime_stabilization": build_runtime_stabilization(truth),
        "recovery_coordination": build_recovery_coordination(truth),
        "runtime_resilience_engine": build_runtime_resilience_engine(truth),
    }
