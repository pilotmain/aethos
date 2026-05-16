# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded runtime state lifecycle sweeps (Phase 2 Step 11)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state

_REPAIR_BUCKET_MAX = 32
_REPAIR_AGE_DAYS = 14
_DEPLOY_TRACE_MAX = 48


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def sweep_stale_repair_contexts(st: dict[str, Any] | None = None, *, persist: bool = True) -> int:
    """Trim old repair buckets; keep latest_by_project pointers valid."""
    state = st if st is not None else load_runtime_state()
    repairs = state.get("repair_contexts")
    if not isinstance(repairs, dict):
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=_REPAIR_AGE_DAYS)
    removed = 0
    for pid, bucket in list(repairs.items()):
        if pid == "latest_by_project" or not isinstance(bucket, dict):
            continue
        for rid, row in list(bucket.items()):
            if not isinstance(row, dict):
                bucket.pop(rid, None)
                removed += 1
                continue
            ts = _parse_iso(str(row.get("updated_at") or row.get("created_at") or ""))
            if ts and ts < cutoff:
                bucket.pop(rid, None)
                removed += 1
        if len(bucket) > _REPAIR_BUCKET_MAX:
            keys = sorted(bucket.keys(), key=lambda k: str((bucket.get(k) or {}).get("updated_at") or ""))
            for k in keys[: len(bucket) - _REPAIR_BUCKET_MAX]:
                bucket.pop(k, None)
                removed += 1
    if persist and st is None:
        save_runtime_state(state)
    return removed


def sweep_deployment_traces(st: dict[str, Any] | None = None, *, persist: bool = True) -> int:
    state = st if st is not None else load_runtime_state()
    traces = state.get("deployment_traces")
    if not isinstance(traces, list):
        return 0
    if len(traces) <= _DEPLOY_TRACE_MAX:
        return 0
    removed = len(traces) - _DEPLOY_TRACE_MAX
    del traces[:removed]
    if persist and st is None:
        save_runtime_state(state)
    return removed


def run_runtime_lifecycle_sweeps() -> dict[str, int]:
    """Single entry for bounded cleanup before truth builds."""
    st = load_runtime_state()
    from app.runtime.runtime_agents import sweep_expired_agents

    agents = sweep_expired_agents(st, persist=False)
    repairs = sweep_stale_repair_contexts(st, persist=False)
    deploy = sweep_deployment_traces(st, persist=False)
    save_runtime_state(st)
    return {"agents_expired": agents, "repair_rows_removed": repairs, "deployment_traces_trimmed": deploy}
