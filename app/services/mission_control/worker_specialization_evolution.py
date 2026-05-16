# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Worker specialization and learning metrics (Phase 4 Step 1)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.worker_accountability import build_worker_accountability


def build_worker_learning_state(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    acc = build_worker_accountability(truth)
    return {
        "reliability_baseline": acc.get("reliability"),
        "failure_rate": acc.get("escalation_rate"),
        "learning_mode": "orchestrator_owned",
        "adaptation_bounded": True,
    }


def build_worker_specialization_confidence(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    workers = ((truth.get("runtime_workers") or {}).get("workers") or [])[:16]
    specs: dict[str, float] = {}
    for w in workers:
        if not isinstance(w, dict):
            continue
        role = str(w.get("role") or "general")
        specs[role] = round(min(1.0, specs.get(role, 0.5) + 0.1), 3)
    return {"by_role": specs, "dominant_role": max(specs, key=specs.get) if specs else None}


def build_worker_collaboration_quality(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    collab = (truth.get("runtime_cohesion") or {}).get("worker_collaboration") or {}
    chains = collab.get("chains") if isinstance(collab, dict) else []
    n = len(chains) if isinstance(chains, list) else 0
    return {"chain_count": n, "quality_score": 0.85 if n else 0.7, "visible": True}


def build_worker_adaptation_metrics(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "worker_learning_state": build_worker_learning_state(truth),
        "worker_specialization_confidence": build_worker_specialization_confidence(truth),
        "worker_collaboration_quality": build_worker_collaboration_quality(truth),
        "orchestrator_owned": True,
    }
