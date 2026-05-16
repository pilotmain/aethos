# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Adaptive operational throttling under pressure (Phase 4 Step 7)."""

from __future__ import annotations

from typing import Any


def build_runtime_operational_throttling(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    pressure = (truth.get("operational_pressure") or {}).get("level", "low")
    high = pressure == "high"
    return {
        "active": high,
        "pressure_level": pressure,
        "advisory_deferred": high,
        "historical_recomputation_delayed": high,
        "event_aggregation_shrunk": high,
        "office_prioritized": True,
        "office_interval_ms": 8000 if high else 12000,
        "advisory_refresh_ms": 30000 if high else 15000,
        "deferred_operations": ["forecasts", "maturity_trends"] if high else [],
        "never_suppresses": ["critical_failures", "governance_visibility", "operator_actions"],
        "advisory_only": True,
    }


def build_responsiveness_score(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    perf = truth.get("runtime_performance_intelligence") or {}
    score = float(perf.get("operational_responsiveness_score") or 0.8)
    return {
        "score": score,
        "target_warm_office_ms": 500,
        "target_cold_office_ms": 3000,
        "meets_warm_target": (truth.get("hydration_metrics") or {}).get("last_hydration_ms", 9999) < 500,
        "enterprise_grade": score >= 0.75,
    }
