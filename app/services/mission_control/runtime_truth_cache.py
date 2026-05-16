# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Short-TTL cache for authoritative runtime truth (Phase 2 Step 11)."""

from __future__ import annotations

import time
from typing import Any, Callable

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_CACHE_TTL_SEC = 5.0


def get_cached_runtime_truth(
    user_id: str | None,
    builder: Callable[[str | None], dict[str, Any]],
) -> dict[str, Any]:
    st = load_runtime_state()
    cache = st.setdefault("mc_runtime_truth_cache", {})
    if not isinstance(cache, dict):
        cache = {}
        st["mc_runtime_truth_cache"] = cache
    key = (user_id or "").strip() or "_global"
    now = time.monotonic()
    entry = cache.get(key)
    if isinstance(entry, dict):
        ts = float(entry.get("_mono_ts") or 0)
        if now - ts < _CACHE_TTL_SEC and isinstance(entry.get("truth"), dict):
            return dict(entry["truth"])
    truth = builder(user_id)
    cache[key] = {"truth": truth, "_mono_ts": now, "updated_at": utc_now_iso()}
    save_runtime_state(st)
    return truth


def invalidate_runtime_truth_cache(user_id: str | None = None) -> None:
    st = load_runtime_state()
    cache = st.get("mc_runtime_truth_cache")
    if not isinstance(cache, dict):
        return
    if user_id:
        cache.pop((user_id or "").strip() or "_global", None)
    else:
        cache.clear()
    save_runtime_state(st)
