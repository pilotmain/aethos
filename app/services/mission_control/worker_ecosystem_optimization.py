# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Worker ecosystem optimization (Phase 4 Step 3)."""

from __future__ import annotations

from typing import Any


def build_worker_optimization_quality(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    health = (truth or {}).get("worker_ecosystem_health") or {}
    collab = (truth or {}).get("worker_coordination_quality") or {}
    score = float(health.get("health_score") or collab.get("collaboration_score") or 0.8)
    return {"score": round(score, 3), "advisory": True}


def build_worker_operational_coordination(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    return {
        "coordination_quality": truth.get("worker_coordination_quality"),
        "specialization_map": truth.get("worker_specialization_map"),
        "workload_balanced": ((truth.get("runtime_workers") or {}).get("active_count") or 0) < 12,
        "orchestrator_owned": True,
    }


def build_worker_ecosystem_maturity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    health = (truth or {}).get("worker_ecosystem_health") or {}
    return {
        "status": health.get("status", "healthy"),
        "health_score": health.get("health_score"),
        "growth": (truth or {}).get("worker_operational_growth"),
    }


def build_adaptive_worker_ecosystem(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "worker_optimization_quality": build_worker_optimization_quality(truth),
        "worker_operational_coordination": build_worker_operational_coordination(truth),
        "worker_ecosystem_maturity": build_worker_ecosystem_maturity(truth),
        "advisory": True,
    }
