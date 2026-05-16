# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Incremental operational timeline — bounded append and windowing (Phase 3 Step 12)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_MAX_APPEND_BUFFER = 64
_MAX_WINDOW = 48


def append_timeline_entry(entry: dict[str, Any]) -> None:
    st = load_runtime_state()
    buf = st.setdefault("timeline_append_buffer", [])
    if isinstance(buf, list):
        row = {**entry, "appended_at": utc_now_iso()}
        buf.append(row)
        if len(buf) > _MAX_APPEND_BUFFER:
            del buf[: len(buf) - _MAX_APPEND_BUFFER]
        st["timeline_append_buffer"] = buf
    save_runtime_state(st)


def _merge_timeline_entries(*, fetch_limit: int) -> list[dict[str, Any]]:
    from app.services.runtime_governance import build_governance_timeline

    base = build_governance_timeline(limit=fetch_limit)
    entries = list(base.get("timeline") or [])
    st = load_runtime_state()
    buf = st.get("timeline_append_buffer") or []
    if isinstance(buf, list):
        entries.extend(r for r in buf if isinstance(r, dict))
    entries.sort(key=lambda e: str(e.get("at") or ""), reverse=True)
    return entries


def _group_entries(entries: list[dict[str, Any]], group_by: str | None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    key_field = {
        "severity": "severity",
        "actor": "who",
        "deployment": "kind",
        "worker": "who",
        "kind": "kind",
    }.get(group_by or "kind", "kind")
    for e in entries:
        bucket = str(e.get(key_field) or e.get("kind") or "other")
        grouped.setdefault(bucket, []).append(e)
    return grouped


def build_incremental_timeline(*, limit: int = 40, severity: str | None = None) -> dict[str, Any]:
    entries = _merge_timeline_entries(fetch_limit=min(int(limit) + 32, 96))
    if severity:
        entries = [e for e in entries if str(e.get("severity") or "") == severity or e.get("kind") == severity]
    grouped = _group_entries(entries, "kind")
    windowed = entries[: min(int(limit), _MAX_WINDOW)]
    raw_n = len(entries)
    summary_ratio = round(len(windowed) / max(1, raw_n), 4) if raw_n else 1.0
    _record_timeline_summary_ratio(summary_ratio)
    return {
        "timeline": windowed,
        "grouped_by_kind": {k: v[:8] for k, v in list(grouped.items())[:12]},
        "entry_count": len(windowed),
        "incremental": True,
        "summary": {"windowed": len(windowed), "raw": raw_n},
    }


def build_timeline_window(
    *,
    limit: int = 24,
    offset: int = 0,
    group_by: str | None = None,
    severity: str | None = None,
) -> dict[str, Any]:
    from app.core.config import get_settings

    max_page = int(getattr(get_settings(), "aethos_timeline_page_max", 48))
    limit = max(1, min(int(limit), max_page))
    entries = _merge_timeline_entries(fetch_limit=limit + offset + 48)
    if severity:
        entries = [e for e in entries if str(e.get("severity") or "") == severity or e.get("kind") == severity]
    total = len(entries)
    page = entries[offset : offset + limit]
    grouped = _group_entries(page, group_by) if group_by else _group_entries(page, "kind")
    return {
        "timeline": page,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
        "grouped": {k: v[:6] for k, v in list(grouped.items())[:16]},
        "incremental": True,
    }


def search_timeline_entries(
    query: str | None = None,
    *,
    limit: int = 24,
    offset: int = 0,
    kind: str | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    entries = _merge_timeline_entries(fetch_limit=120)
    q = (query or "").strip().lower()
    if q:
        entries = [
            e
            for e in entries
            if q in " ".join(str(e.get(k) or "") for k in ("what", "who", "kind", "provider")).lower()
        ]
    if kind:
        entries = [e for e in entries if str(e.get("kind") or "") == kind]
    if actor:
        a = actor.lower()
        entries = [e for e in entries if a in str(e.get("who") or "").lower()]
    total = len(entries)
    page = entries[offset : offset + limit]
    return {"entries": page, "total": total, "offset": offset, "limit": limit, "query": query}


def _record_timeline_summary_ratio(ratio: float) -> None:
    try:
        from app.runtime.runtime_state import load_runtime_state, save_runtime_state

        st = load_runtime_state()
        m = st.setdefault("payload_discipline_metrics", {})
        if isinstance(m, dict):
            m["timeline_summary_ratio"] = ratio
            save_runtime_state(st)
    except Exception:
        pass
