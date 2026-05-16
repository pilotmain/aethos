# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator productivity and workflow acceleration metrics (Phase 4 Step 1)."""

from __future__ import annotations

from typing import Any


def build_operator_productivity_metrics(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    perf = truth.get("operational_performance_completion") or {}
    within = (perf.get("mission_control_responsiveness") or {}).get("within_target", False)
    return {
        "mc_responsiveness_within_target": within,
        "workflow_completion_quality": (truth.get("operational_quality") or {}).get("quality_score"),
        "navigation_cohesion": truth.get("runtime_identity") is not None,
        "governance_searchable": (truth.get("governance_experience") or {}).get("searchable"),
    }


def build_operational_acceleration(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "slice_apis_available": True,
        "incremental_hydration": True,
        "estimated_time_saved_pct": 0.35 if (truth.get("runtime_performance") or {}).get("cache_hit_rate") else 0.15,
        "advisory": True,
    }


def build_workflow_efficiency(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    eff = (truth or {}).get("runtime_query_efficiency") or {}
    return {
        "cache_reuse_rate": eff.get("cache_reuse_rate"),
        "hydration_ms": eff.get("last_hydration_ms"),
        "efficient": bool(eff.get("derived_metric_reuse")),
    }


def build_enterprise_productivity_signals(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "operator_productivity_metrics": build_operator_productivity_metrics(truth),
        "operational_acceleration": build_operational_acceleration(truth),
        "workflow_efficiency": build_workflow_efficiency(truth),
    }
