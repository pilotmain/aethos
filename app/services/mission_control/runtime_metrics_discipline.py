# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime performance discipline metrics (Phase 3 Step 3)."""

from __future__ import annotations

import json
from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_MAX_SAMPLES = 32


def record_truth_build(*, payload_keys: int, approx_bytes: int, cache_hit: bool) -> None:
    st = load_runtime_state()
    m = st.setdefault("runtime_discipline_metrics", {})
    if not isinstance(m, dict):
        m = {}
        st["runtime_discipline_metrics"] = m
    m["last_truth_build_at"] = utc_now_iso()
    m["last_payload_key_count"] = payload_keys
    m["last_payload_approx_bytes"] = approx_bytes
    hits = int(m.get("truth_cache_hits") or 0)
    misses = int(m.get("truth_cache_misses") or 0)
    if cache_hit:
        m["truth_cache_hits"] = hits + 1
    else:
        m["truth_cache_misses"] = misses + 1
    total = hits + misses + (1 if cache_hit else 1)
    m["truth_cache_hit_rate"] = round((m.get("truth_cache_hits") or 0) / max(1, total), 4)
    hist = m.setdefault("payload_samples", [])
    if isinstance(hist, list):
        hist.append({"at": utc_now_iso(), "bytes": approx_bytes, "keys": payload_keys})
        if len(hist) > _MAX_SAMPLES:
            del hist[: len(hist) - _MAX_SAMPLES]
    save_runtime_state(st)


def get_runtime_discipline_metrics() -> dict[str, Any]:
    st = load_runtime_state()
    m = st.get("runtime_discipline_metrics") or {}
    if not isinstance(m, dict):
        return {}
    buf = st.get("runtime_event_buffer") or []
    return {
        **m,
        "event_buffer_size": len(buf) if isinstance(buf, list) else 0,
        "event_summaries_size": len(st.get("runtime_event_summaries") or []),
    }


def approx_payload_bytes(truth: dict[str, Any]) -> int:
    try:
        return len(json.dumps(truth, default=str))
    except (TypeError, ValueError):
        return 0
