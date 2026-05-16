# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Unified worker operational state and cohesion (Phase 3 Step 15)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_identity import CANONICAL_LABELS
from app.services.mission_control.runtime_worker_visibility import build_runtime_workers_view
from app.services.mission_control.worker_accountability import build_worker_accountability


def build_unified_worker_state(truth: dict[str, Any] | None = None, *, user_id: str | None = None) -> dict[str, Any]:
    view = (truth or {}).get("runtime_workers") or build_runtime_workers_view(user_id)
    workers = list(view.get("workers") or []) if isinstance(view, dict) else []
    return {
        "orchestrator": view.get("orchestrator"),
        "workers": workers[:24],
        "active_count": view.get("active_count"),
        "label": CANONICAL_LABELS["worker"],
    }


def build_worker_operational_identity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    acc = (truth or {}).get("worker_accountability") or build_worker_accountability(truth)
    return {
        "role": CANONICAL_LABELS["worker"],
        "orchestrator_owned": True,
        "reliability": acc.get("reliability"),
        "active_workers": acc.get("active_workers"),
        "governed": True,
    }


def build_worker_runtime_cohesion(truth: dict[str, Any] | None = None, *, user_id: str | None = None) -> dict[str, Any]:
    return {
        "unified_state": build_unified_worker_state(truth, user_id=user_id),
        "identity": build_worker_operational_identity(truth),
        "accountability": (truth or {}).get("worker_accountability"),
        "governance": (truth or {}).get("worker_governance"),
        "quality": (truth or {}).get("worker_operational_quality"),
        "deliverables_bounded": len((truth or {}).get("worker_deliverables") or []),
        "cohesive": True,
    }
