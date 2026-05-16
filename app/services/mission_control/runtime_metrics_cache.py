# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded cached metric snapshots for Mission Control (Phase 2 Step 9)."""

from __future__ import annotations

import time
from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_CACHE_TTL_SEC = 5.0
_HISTORY_MAX = 48


def _cache_bucket(st: dict[str, Any]) -> dict[str, Any]:
    c = st.setdefault("mc_metrics_cache", {})
    return c if isinstance(c, dict) else {}


def get_cached_metrics(
    user_id: str,
    builder: Any,
) -> dict[str, Any]:
    """Return cached metrics or rebuild via ``builder(user_id)``."""
    st = load_runtime_state()
    cache = _cache_bucket(st)
    key = (user_id or "").strip() or "_global"
    now = time.monotonic()
    entry = cache.get(key)
    if isinstance(entry, dict):
        ts = float(entry.get("_mono_ts") or 0)
        if now - ts < _CACHE_TTL_SEC and isinstance(entry.get("metrics"), dict):
            return dict(entry["metrics"])
    metrics = builder(user_id)
    cache[key] = {"metrics": metrics, "_mono_ts": now, "updated_at": utc_now_iso()}
    hist = st.setdefault("mc_metrics_history", [])
    if not isinstance(hist, list):
        hist = []
        st["mc_metrics_history"] = hist
    hist.append({"user_id": key, "updated_at": utc_now_iso(), "snapshot_keys": list(metrics.keys())[:24]})
    if len(hist) > _HISTORY_MAX:
        del hist[: len(hist) - _HISTORY_MAX]
    save_runtime_state(st)
    return metrics


def invalidate_metrics_cache(user_id: str | None = None) -> None:
    st = load_runtime_state()
    cache = _cache_bucket(st)
    if user_id:
        cache.pop((user_id or "").strip(), None)
    else:
        cache.clear()
    save_runtime_state(st)
