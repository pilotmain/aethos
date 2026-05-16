# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lazy runtime views — on-demand intelligence panels (Phase 4 Step 6)."""

from __future__ import annotations

import time
from typing import Any

from app.services.mission_control.runtime_hydration_scheduler import defer_metric

LAZY_VIEW_NAMES = frozenset(
    {"routing", "posture", "continuity", "advisories", "strategy", "recovery", "governance"}
)


def build_lazy_view(view_name: str, user_id: str | None = None) -> dict[str, Any]:
    """Build a single operational view without full truth assembly when possible."""
    name = (view_name or "").strip().lower()
    if name not in LAZY_VIEW_NAMES:
        return {"error": "unknown_view", "available": sorted(LAZY_VIEW_NAMES)}

    t0 = time.monotonic()
    from app.services.mission_control.runtime_resilience import fetch_slice_resilient

    if name == "routing":
        from app.services.mission_control.runtime_truth_cache import get_cached_runtime_truth
        from app.services.mission_control.runtime_truth import build_runtime_truth

        try:
            t = get_cached_runtime_truth(user_id, lambda uid: build_runtime_truth(user_id=uid))
            payload = t.get("intelligent_routing") or {}
            status = "healthy"
        except Exception:
            data, status = fetch_slice_resilient("intelligence", user_id)
            payload = (data or {}).get("intelligent_routing") or {}
    elif name == "posture":
        from app.services.mission_control.runtime_truth_cache import get_cached_runtime_truth
        from app.services.mission_control.runtime_truth import build_runtime_truth

        try:
            t = get_cached_runtime_truth(user_id, lambda uid: build_runtime_truth(user_id=uid))
            payload = {
                "runtime_awareness": t.get("runtime_awareness"),
                "enterprise_operational_posture": t.get("enterprise_operational_posture"),
            }
            status = "healthy"
        except Exception:
            data, status = fetch_slice_resilient("health", user_id)
            payload = data
    elif name == "continuity":
        data, status = fetch_slice_resilient("continuity", user_id)
        payload = data
    elif name == "advisories":
        from app.services.mission_control.runtime_advisories import build_runtime_advisory_engine

        data, status = fetch_slice_resilient("recommendations", user_id)
        payload = build_runtime_advisory_engine(data if isinstance(data, dict) else {})
    elif name == "strategy":
        from app.services.mission_control.strategic_runtime_planning import build_strategic_runtime_planning

        data, status = fetch_slice_resilient("intelligence", user_id)
        payload = build_strategic_runtime_planning(data if isinstance(data, dict) else {})
    elif name == "recovery":
        from app.services.mission_control.runtime_recovery_center import build_runtime_recovery_center

        payload = build_runtime_recovery_center(user_id=user_id)
        status = payload.get("operational_status", "healthy")
    elif name == "governance":
        data, status = fetch_slice_resilient("governance", user_id)
        payload = data
    else:
        payload = {}
        status = "partial"

    elapsed = round((time.monotonic() - t0) * 1000.0, 2)
    defer_metric(lazy_load_metrics={name: elapsed})
    return {
        "view": name,
        "payload": payload,
        "operational_status": status,
        "build_ms": elapsed,
    }
