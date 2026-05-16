# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Adaptive runtime coordination — advisory, explainable (Phase 4 Step 2)."""

from __future__ import annotations

from typing import Any


def build_adaptive_execution_signals(truth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    truth = truth or {}
    signals: list[dict[str, Any]] = []
    pressure = truth.get("operational_pressure") or {}
    if pressure.get("queue_pressure"):
        signals.append(
            {
                "domain": "worker_assignment",
                "suggestion": "Stagger worker assignments to reduce queue pressure.",
                "advisory": True,
            }
        )
    if (truth.get("routing_summary") or {}).get("fallback_used"):
        signals.append(
            {
                "domain": "provider_selection",
                "suggestion": "Review primary provider health before next deployment.",
                "advisory": True,
            }
        )
    repairs = len(((truth.get("runtime_escalations") or {}).get("active_escalations") or []))
    if repairs > 2:
        signals.append(
            {
                "domain": "repair_routing",
                "suggestion": "Consolidate repair contexts — multiple active escalations.",
                "advisory": True,
            }
        )
    return signals[:10]


def build_coordination_quality(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    collab = (truth.get("worker_collaboration_quality") or {}).get("quality_score", 0.7)
    cohesion = (truth.get("runtime_cohesion") or {}).get("cohesion_score")
    score = float(cohesion if cohesion is not None else collab)
    return {
        "score": round(score, 3),
        "worker_collaboration": collab,
        "orchestrator_owned": True,
        "advisory": True,
    }


def build_runtime_balancing(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    pressure = truth.get("operational_pressure") or {}
    return {
        "pressure_level": pressure.get("level", "low"),
        "queue_pressure": bool(pressure.get("queue_pressure")),
        "balanced": pressure.get("level") != "high",
        "continuity_prioritized": bool(truth.get("operator_continuity")),
    }


def build_adaptive_coordination(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    signals = build_adaptive_execution_signals(truth)
    return {
        "advisory_first": True,
        "runtime_visible": True,
        "explainable": True,
        "operator_review_required": True,
        "adaptive_execution_signals": signals,
        "domains": sorted({s.get("domain") for s in signals if s.get("domain")}),
    }
