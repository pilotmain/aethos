# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Worker ecosystem evolution (Phase 4 Step 2)."""

from __future__ import annotations

from typing import Any


def build_worker_specialization_map(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    specs = (truth or {}).get("worker_specialization_confidence") or {}
    by_role = specs.get("by_role") if isinstance(specs, dict) else {}
    return {"by_role": by_role, "dominant_role": specs.get("dominant_role")}


def build_worker_coordination_quality(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    collab = (truth or {}).get("worker_collaboration_quality") or {}
    cohesion = (truth.get("worker_runtime_cohesion") or {}) if truth else {}
    return {
        "collaboration_score": collab.get("quality_score"),
        "cohesion_visible": bool(cohesion),
        "chain_count": collab.get("chain_count", 0),
        "orchestrator_owned": True,
    }


def build_worker_operational_growth(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    learning = (truth or {}).get("worker_learning_state") or {}
    return {
        "reliability_baseline": learning.get("reliability_baseline"),
        "learning_mode": learning.get("learning_mode", "orchestrator_owned"),
        "adaptation_bounded": learning.get("adaptation_bounded", True),
    }


def build_worker_ecosystem_health(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    acc = truth.get("worker_accountability") or {}
    rel = float(acc.get("reliability") or 0.8)
    active = ((truth.get("runtime_workers") or {}).get("active_count")) or 0
    return {
        "health_score": round(rel, 3),
        "active_workers": active,
        "status": "healthy" if rel >= 0.75 and active < 12 else ("busy" if active >= 12 else "review"),
        "specialization_recommendations": _specialization_recommendations(truth),
    }


def _specialization_recommendations(truth: dict[str, Any]) -> list[str]:
    specs = build_worker_specialization_map(truth).get("by_role") or {}
    if not specs:
        return ["Maintain general worker roles until specialization confidence grows."]
    dominant = max(specs, key=specs.get) if specs else None
    if dominant:
        return [f"Reinforce {dominant} specialization — highest confidence role."]
    return []
