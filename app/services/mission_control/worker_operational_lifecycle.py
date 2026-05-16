# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Worker operational lifecycle maturity (Phase 4 Step 8)."""

from __future__ import annotations

from typing import Any

LIFECYCLE_STAGES = ("spawned", "active", "specialized", "trusted", "archived", "summarized", "historical")


def build_worker_lifecycle_maturity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    workers = truth.get("runtime_workers") or {}
    active = int(workers.get("active_count") or 0)
    return {
        "maturity_level": "enterprise" if active >= 4 else "growing",
        "active_workers": active,
        "stages": list(LIFECYCLE_STAGES),
    }


def build_worker_specialization_trust(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "confidence": (truth or {}).get("worker_specialization_confidence"),
        "map": (truth or {}).get("worker_specialization_map"),
    }


def build_lifecycle_governance(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"orchestrator_owned": True, "bounded": True, "explainable": True}


def build_operational_worker_lineage(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ownership_trace_available": bool((truth or {}).get("ownership_trace")), "bounded": True}


def build_worker_operational_lifecycle(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "worker_lifecycle_maturity": build_worker_lifecycle_maturity(truth),
        "worker_specialization_trust": build_worker_specialization_trust(truth),
        "lifecycle_governance": build_lifecycle_governance(truth),
        "operational_worker_lineage": build_operational_worker_lineage(truth),
    }
