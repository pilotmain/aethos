# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operational recovery center — enterprise visibility (Phase 4 Step 6)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state


def build_runtime_recovery_center(
    truth: dict[str, Any] | None = None,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    truth = truth or {}
    st = load_runtime_state()
    hm = st.get("hydration_metrics") or {}
    resilience = truth.get("runtime_resilience") or {}
    recovery = truth.get("operational_recovery_state") or {}
    integrity = truth.get("runtime_truth_integrity") or {}

    failed_slices: list[str] = []
    if isinstance(hm, dict):
        for k, v in (hm.get("slice_build_times") or {}).items():
            if isinstance(v, (int, float)) and v > 8000:
                failed_slices.append(str(k))

    recommendations: list[dict[str, Any]] = []
    if resilience.get("status") in ("degraded", "partial", "stale"):
        recommendations.append(
            {
                "title": "Use cached truth",
                "detail": "Mission Control can serve stale snapshots while hydration recovers.",
                "advisory_only": True,
            }
        )
    if recovery.get("degradation_signals"):
        recommendations.append(
            {
                "title": "Review degradation signals",
                "detail": "Inspect operational_recovery_state before changing routing.",
                "advisory_only": True,
            }
        )

    status = resilience.get("status") or "healthy"
    if recovery.get("degradation_signals") and status == "healthy":
        status = "recovering"

    return {
        "operational_status": status,
        "failed_slices": failed_slices[:8],
        "hydration_retries": int(hm.get("invalidation_rate") or 0) if isinstance(hm, dict) else 0,
        "stale_caches": bool(resilience.get("using_cached_truth")),
        "degraded_panels": list(resilience.get("failed_endpoints") or [])[:8],
        "failed_routes": [],
        "runtime_pressure": truth.get("operational_pressure") or {},
        "recovery_recommendations": recommendations[:6],
        "hydration_generation_id": hm.get("hydration_generation_id") if isinstance(hm, dict) else None,
        "hydration_duration_ms": hm.get("hydration_duration_ms") if isinstance(hm, dict) else None,
        "truth_integrity_score": integrity.get("truth_integrity_score"),
        "continuity_engine": truth.get("operational_continuity_engine") or {},
    }
