# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Worker accountability and operational quality (Phase 3 Step 14)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.runtime_worker_visibility import build_runtime_workers_view


def build_worker_accountability(truth: dict[str, Any] | None = None, *, user_id: str | None = None) -> dict[str, Any]:
    view = (truth or {}).get("runtime_workers") or build_runtime_workers_view(user_id)
    workers = list(view.get("workers") or []) if isinstance(view, dict) else []
    st = load_runtime_state()
    deliverables = st.get("worker_deliverables") or {}
    dn = len(deliverables) if isinstance(deliverables, dict) else 0
    active = int(view.get("active_count") or 0) if isinstance(view, dict) else 0
    failed = sum(1 for w in workers if str(w.get("status") or "").lower() in ("failed", "error"))
    return {
        "active_workers": active,
        "total_workers": len(workers),
        "deliverable_count": dn,
        "failed_workers": failed,
        "reliability": _clamp(1.0 - (failed / max(1, len(workers)))),
        "escalation_rate": round(failed / max(1, active or 1), 4),
    }


def build_worker_governance(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    eff = (truth or {}).get("worker_effectiveness") or {}
    return {
        "governed": True,
        "operator_approved_delegation": True,
        "effectiveness": eff if isinstance(eff, dict) else {},
    }


def build_worker_operational_quality(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    acc = build_worker_accountability(truth)
    return {
        "quality_score": acc.get("reliability"),
        "deliverable_pressure": acc.get("deliverable_count"),
        "specialization_visible": True,
    }


def build_worker_trust(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    acc = build_worker_accountability(truth)
    return {"score": acc.get("reliability", 0.8), "summary": "worker accountability derived from runtime state"}


def _clamp(v: float) -> float:
    return round(max(0.0, min(1.0, v)), 3)
