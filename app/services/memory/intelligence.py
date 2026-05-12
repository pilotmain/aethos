# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Post-mission memory hygiene — scoring, pruning, optional consolidation (Phase 41)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.services.logging.logger import get_logger
from app.services.memory.memory_store import MemoryStore

_log = get_logger("memory.intelligence")

# Below this heuristic score, entries are candidates for prune when over capacity.
MIN_IMPORTANCE_SCORE_FOR_KEEP: float = 0.5


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def score_entry(entry: dict[str, Any]) -> float:
    """Heuristic importance: recency + mission summaries weighted above noise."""
    base = 1.0
    kind = str(entry.get("type") or "")
    if kind == "mission_summary":
        base += 3.0
    ts = _parse_ts(str(entry.get("ts") or ""))
    if ts:
        age_days = max(0.0, (datetime.now(timezone.utc) - ts.replace(tzinfo=timezone.utc)).days)
        base += max(0.0, 14.0 - age_days) * 0.15
    meta = entry.get("meta")
    if isinstance(meta, dict) and meta.get("mission_id"):
        base += 0.5
    return base


def prune_old_entries(
    user_id: str,
    *,
    max_entries: int = 300,
    store: MemoryStore | None = None,
) -> dict[str, Any]:
    """
    Drop lowest-scoring rows when over ``max_entries``.

    Returns counts for observability.
    """
    st = store or MemoryStore()
    rows = st.list_entries(user_id, limit=2000)
    if len(rows) <= max_entries:
        return {"ok": True, "removed": 0, "kept": len(rows)}
    scored = [(score_entry(r), r) for r in rows]
    scored.sort(key=lambda x: x[0], reverse=True)
    keep_set = {str(x[1].get("id") or "") for x in scored[:max_entries]}
    removed = 0
    for _sc, row in scored[max_entries:]:
        eid = str(row.get("id") or "")
        if eid and eid not in keep_set:
            if st.remove_entry(user_id, eid):
                removed += 1
    return {"ok": True, "removed": removed, "kept": len(rows) - removed}


def summarize_mission_append_body(meta: dict[str, Any], *, timed_out: bool) -> str | None:
    """Optional one-line consolidation hint stored in meta (caller merges into entry)."""
    mid = str(meta.get("mission_id") or "")
    if not mid:
        return None
    status = "timeout" if timed_out else "completed"
    return json.dumps({"phase41_summary_stub": True, "mission_id": mid, "status": status}, sort_keys=True)


def maybe_post_mission_memory_pass(user_id: str, *, store: MemoryStore | None = None) -> dict[str, Any]:
    """After writing mission memory: lightweight prune so the index does not grow without bound."""
    try:
        return prune_old_entries(user_id, max_entries=350, store=store)
    except OSError as exc:
        _log.warning("memory.intelligence prune failed: %s", exc)
        return {"ok": False, "error": str(exc)}


__all__ = [
    "maybe_post_mission_memory_pass",
    "prune_old_entries",
    "score_entry",
    "summarize_mission_append_body",
]
