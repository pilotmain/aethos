# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Governance indexing discipline — bounded search acceleration (Phase 4 Step 8)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_MAX_BUCKETS = 32


def build_governance_operational_index(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    tl = truth.get("unified_operational_timeline") or {}
    entries = int(tl.get("entry_count") or 0)
    kinds: dict[str, int] = {}
    for e in (tl.get("entries") or [])[:40]:
        if isinstance(e, dict):
            k = str(e.get("kind") or "other")
            kinds[k] = kinds.get(k, 0) + 1
    st = load_runtime_state()
    idx = st.setdefault("governance_operational_index", {})
    if isinstance(idx, dict):
        buckets = list(idx.get("buckets") or [])
        buckets.append({"at": utc_now_iso(), "entries": entries, "kinds": kinds})
        if len(buckets) > _MAX_BUCKETS:
            buckets = buckets[-_MAX_BUCKETS:]
        idx["buckets"] = buckets
        idx["updated_at"] = utc_now_iso()
        st["governance_operational_index"] = idx
        save_runtime_state(st)
    return {
        "governance_index_health": {"healthy": entries < 500, "entry_count": entries},
        "timeline_window_efficiency": {"bounded": True, "bucket_count": len(kinds)},
        "governance_query_cost": "low" if entries < 200 else "medium",
        "kind_partitions": kinds,
        "summarized_historical": entries > 80,
    }
