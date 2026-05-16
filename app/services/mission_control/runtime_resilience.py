# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control runtime resilience — degraded modes and partial recovery (Phase 4 Step 6)."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from app.runtime.runtime_state import load_runtime_state, utc_now_iso

logger = logging.getLogger(__name__)

OPERATIONAL_STATES = frozenset({"healthy", "degraded", "recovering", "partial", "offline", "stale"})


def _stale_truth_entry(user_id: str | None) -> dict[str, Any] | None:
    st = load_runtime_state()
    cache = st.get("mc_runtime_truth_cache") or {}
    if not isinstance(cache, dict):
        return None
    key = (user_id or "").strip() or "_global"
    entry = cache.get(key)
    if isinstance(entry, dict) and isinstance(entry.get("truth"), dict):
        return dict(entry["truth"])
    return None


def fetch_slice_resilient(
    slice_name: str,
    user_id: str | None,
    *,
    fallback: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    """Return slice payload and operational status; never raise to callers."""
    from app.services.mission_control.runtime_hydration import get_lightweight_slice

    try:
        data = get_lightweight_slice(slice_name, user_id)
        if data:
            return data, "healthy"
    except Exception as exc:
        logger.warning("slice %s failed: %s", slice_name, exc)

    stale = _stale_truth_entry(user_id)
    if stale:
        office = stale.get("office")
        if slice_name == "workers" and isinstance(office, dict):
            return {"office": office, **(fallback or {})}, "stale"
        if slice_name in stale:
            return {slice_name: stale.get(slice_name), **(fallback or {})}, "stale"

    return dict(fallback or {}), "degraded" if fallback else "partial"


def build_runtime_resilience_block(
    *,
    status: str = "healthy",
    failed_endpoints: list[str] | None = None,
    using_cached_truth: bool = False,
) -> dict[str, Any]:
    st = load_runtime_state()
    attempts = int(st.get("connection_repair_attempts") or 0)
    return {
        "status": status if status in OPERATIONAL_STATES else "degraded",
        "failed_endpoints": failed_endpoints or [],
        "using_cached_truth": using_cached_truth,
        "connection_repair_attempts": attempts,
        "last_successful_health_check": st.get("last_successful_health_check"),
        "last_runtime_version": st.get("last_runtime_version") or "phase4_step6",
        "advisory_only": True,
        "updated_at": utc_now_iso(),
    }


def build_execution_snapshot_resilient(
    db: Any,
    *,
    user_id: str | None,
    hours: int,
    builder: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    """Wrap execution snapshot — return degraded payload instead of raising."""
    failed: list[str] = []
    t0 = time.monotonic()
    try:
        out = builder(db, user_id=user_id, hours=hours)
        out["runtime_resilience"] = build_runtime_resilience_block(status="healthy")
        out["operational_status"] = "healthy"
        return out
    except Exception as exc:
        logger.exception("mission_control_state degraded: %s", exc)
        failed.append("state")
        stale = _stale_truth_entry(user_id) or {}
        partial = {
            "operational_status": "degraded",
            "runtime_resilience": build_runtime_resilience_block(
                status="degraded",
                failed_endpoints=failed,
                using_cached_truth=bool(stale),
            ),
            "office": stale.get("office") or {},
            "runtime_agents": stale.get("runtime_agents") or [],
            "routing_summary": stale.get("routing_summary") or {},
            "panels": stale.get("panels") or {},
            "degraded_reason": str(exc)[:240],
            "snapshot_duration_ms": round((time.monotonic() - t0) * 1000.0, 2),
            "recovery_hint": "Use GET /api/v1/mission-control/runtime-recovery or aethos connection repair",
        }
        return partial
