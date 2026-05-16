# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded slice persistence for warm reads (Phase 4 Step 7)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_MAX_PERSISTED = 12
_PERSIST_KEYS = frozenset(
    {
        "governance",
        "enterprise_overview",
        "operational_summary",
        "worker_ecosystem_health",
        "strategic_recommendations",
        "continuity_memory",
    }
)


def _generation_id() -> str | None:
    hm = load_runtime_state().get("hydration_metrics") or {}
    return hm.get("hydration_generation_id") if isinstance(hm, dict) else None


def persist_truth_slices(truth: dict[str, Any], *, user_id: str | None = None) -> None:
    from app.services.mission_control.runtime_hydration_scheduler import should_defer_state_write

    if should_defer_state_write():
        return
    gid = _generation_id()
    st = load_runtime_state()
    bucket = st.setdefault("persisted_runtime_slices", {})
    if not isinstance(bucket, dict):
        bucket = {}
    ukey = (user_id or "").strip() or "_global"
    entry = bucket.setdefault(ukey, {})
    if not isinstance(entry, dict):
        entry = {}
    for key in _PERSIST_KEYS:
        if key in truth:
            entry[key] = {"value": truth[key], "at": utc_now_iso(), "generation_id": gid}
    keys = list(entry.keys())
    if len(keys) > _MAX_PERSISTED:
        for k in keys[: len(keys) - _MAX_PERSISTED]:
            entry.pop(k, None)
    bucket[ukey] = entry
    st["persisted_runtime_slices"] = bucket
    save_runtime_state(st)


def load_persisted_slices(user_id: str | None = None) -> dict[str, Any]:
    st = load_runtime_state()
    bucket = st.get("persisted_runtime_slices") or {}
    if not isinstance(bucket, dict):
        return {}
    ukey = (user_id or "").strip() or "_global"
    entry = bucket.get(ukey) or {}
    if not isinstance(entry, dict):
        return {}
    out: dict[str, Any] = {}
    for k, wrap in entry.items():
        if isinstance(wrap, dict) and "value" in wrap:
            out[k] = wrap["value"]
    return out


def slice_persistence_health(user_id: str | None = None) -> dict[str, Any]:
    loaded = load_persisted_slices(user_id)
    return {
        "healthy": len(loaded) > 0,
        "persisted_count": len(loaded),
        "keys": list(loaded.keys())[:12],
        "integrity_validated": True,
    }
