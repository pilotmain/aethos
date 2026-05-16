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


def build_incremental_timeline(*, limit: int = 40, severity: str | None = None) -> dict[str, Any]:
    from app.services.runtime_governance import build_governance_timeline

    base = build_governance_timeline(limit=limit)
    entries = list(base.get("timeline") or [])
    st = load_runtime_state()
    buf = st.get("timeline_append_buffer") or []
    if isinstance(buf, list):
        entries.extend(r for r in buf if isinstance(r, dict))
    if severity:
        entries = [e for e in entries if str(e.get("severity") or "") == severity or e.get("kind") == severity]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        kind = str(e.get("kind") or "other")
        grouped.setdefault(kind, []).append(e)
    entries.sort(key=lambda e: str(e.get("at") or ""), reverse=True)
    windowed = entries[: min(int(limit), _MAX_WINDOW)]
    return {
        "timeline": windowed,
        "grouped_by_kind": {k: v[:8] for k, v in list(grouped.items())[:12]},
        "entry_count": len(windowed),
        "incremental": True,
        "summary": base.get("summary"),
    }
