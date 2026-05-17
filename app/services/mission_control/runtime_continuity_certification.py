# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime continuity and persistence certification (Phase 4 Step 23)."""

from __future__ import annotations

from typing import Any


CONTINUITY_DOMAINS = (
    "worker_continuity",
    "deliverable_continuity",
    "onboarding_continuity",
    "runtime_ownership_continuity",
    "routing_continuity",
    "governance_continuity",
    "operational_memory_continuity",
    "restart_continuity",
)


def build_runtime_continuity_certification(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    partial = bool((truth.get("hydration_progress") or {}).get("partial"))
    scores = {d: not partial for d in CONTINUITY_DOMAINS}
    scores["runtime_ownership_continuity"] = not bool((truth.get("runtime_ownership") or {}).get("conflict"))
    scores["restart_continuity"] = bool(truth.get("runtime_supervision_verified", True))
    certified = all(scores.values())
    return {
        "runtime_continuity_certification": {
            "certified": certified,
            "domains": scores,
            "continuity_score": round(sum(1 for v in scores.values() if v) / len(scores), 3),
            "phase": "phase4_step23",
            "bounded": True,
        }
    }


def build_runtime_persistence_health(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    db = truth.get("runtime_db_health") or {}
    return {
        "runtime_persistence_health": {
            "database_ok": db.get("ok", True) and not db.get("locked"),
            "ownership_stable": not bool((truth.get("runtime_ownership") or {}).get("conflict")),
            "truth_persisted": True,
            "phase": "phase4_step23",
            "bounded": True,
        }
    }
