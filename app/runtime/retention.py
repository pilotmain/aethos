# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded growth: trim planning lists, quarantine, backups (OpenClaw runtime caps)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.runtime.backups.runtime_snapshots import list_runtime_backup_files
from app.runtime.runtime_state import utc_now_iso


def trim_planning_outcomes(st: dict[str, Any], *, limit: int | None = None) -> int:
    lim = int(limit if limit is not None else get_settings().aethos_planning_outcome_limit)
    ol = st.get("planning_outcomes")
    if not isinstance(ol, list) or len(ol) <= lim:
        return 0
    overflow = len(ol) - lim
    st["planning_outcomes"] = ol[-lim:]
    return overflow


def trim_planning_records(st: dict[str, Any], *, limit: int | None = None) -> int:
    """Drop oldest non-active planning rows when over cap (never deletes ``status==active``)."""
    from app.planning.planner_runtime import planning_records

    lim = int(limit if limit is not None else get_settings().aethos_planning_record_limit)
    pr = planning_records(st)
    items = [(k, v) for k, v in pr.items() if isinstance(v, dict)]
    if len(items) <= lim:
        return 0
    active = {str(k) for k, v in items if str(v.get("status") or "").lower() == "active"}
    rest = [(str(k), v) for k, v in items if str(k) not in active]
    rest.sort(key=lambda kv: str(kv[1].get("updated_at") or kv[1].get("created_at") or ""))
    to_drop = len(items) - lim
    removed = 0
    for k, _v in rest[:to_drop]:
        pr.pop(k, None)
        removed += 1
    return removed


def trim_runtime_quarantine(st: dict[str, Any], *, limit: int | None = None) -> int:
    lim = int(limit if limit is not None else get_settings().aethos_runtime_quarantine_limit)
    qc = st.get("runtime_corruption_quarantine")
    if not isinstance(qc, list) or len(qc) <= lim:
        return 0
    overflow = len(qc) - lim
    st["runtime_corruption_quarantine"] = qc[-lim:]
    return overflow


def prune_runtime_backup_files(*, max_keep: int | None = None) -> dict[str, Any]:
    """Delete oldest backup JSON files beyond cap (keeps newest ``max_keep``). Never deletes if <= cap."""
    cap = int(max_keep if max_keep is not None else get_settings().aethos_runtime_backup_limit)
    rows = list_runtime_backup_files(limit=max(cap * 4, cap + 5))
    if len(rows) <= cap:
        return {"deleted": 0, "kept": len(rows)}
    victims = rows[cap:]
    deleted = 0
    for r in victims:
        p = Path(str(r.get("path") or ""))
        if p.is_file():
            try:
                p.unlink()
                deleted += 1
            except OSError:
                pass
    return {"deleted": deleted, "kept": min(len(rows) - deleted, cap)}


def apply_runtime_retention(st: dict[str, Any]) -> dict[str, Any]:
    """Apply caps in-place; return counts for cleanup telemetry."""
    out: dict[str, Any] = {}
    out["planning_outcomes_trimmed"] = trim_planning_outcomes(st)
    out["planning_records_trimmed"] = trim_planning_records(st)
    out["quarantine_trimmed"] = trim_runtime_quarantine(st)
    out["backups"] = prune_runtime_backup_files()
    try:
        from app.runtime.events.runtime_events import emit_runtime_event

        emit_runtime_event(
            st,
            "runtime_retention_pruned",
            **{k: int(v) if isinstance(v, (int, float)) else str(v)[:200] for k, v in out.items()},
        )
    except Exception:
        pass
    rs = st.setdefault("runtime_resilience", {})
    if isinstance(rs, dict):
        rs["last_retention"] = {"ts": utc_now_iso(), **{k: v for k, v in out.items() if k != "backups"}}
        rs["last_retention"]["backups_deleted"] = int((out.get("backups") or {}).get("deleted") or 0)
    return out
