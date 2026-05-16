# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Adaptive planning persistence (reasoning, retries, delegation, quality)."""

from __future__ import annotations

from typing import Any

from app.planning.adaptive_planning_row import ensure_adaptive_planning_fields
from app.runtime.runtime_state import utc_now_iso


def _planning_records(st: dict[str, Any]) -> dict[str, Any]:
    from app.planning.planner_runtime import planning_records

    return planning_records(st)


def _get_planning(st: dict[str, Any], planning_id: str) -> dict[str, Any] | None:
    from app.planning.planner_runtime import get_planning

    return get_planning(st, planning_id)


def append_planning_reasoning(st: dict[str, Any], planning_id: str, *, message: str, detail: dict[str, Any] | None = None) -> None:
    row = _get_planning(st, str(planning_id))
    if not row:
        return
    ensure_adaptive_planning_fields(row)
    ts = utc_now_iso()
    notes = list(row["planning_reasoning"])
    notes.append({"ts": ts, "message": (message or "")[:2000], "detail": dict(detail or {})})
    row["planning_reasoning"] = notes[-500:]
    row["updated_at"] = ts
    _planning_records(st)[str(planning_id)] = row


def append_adaptive_change(st: dict[str, Any], planning_id: str, *, change: str, context: dict[str, Any] | None = None) -> None:
    row = _get_planning(st, str(planning_id))
    if not row:
        return
    ensure_adaptive_planning_fields(row)
    ts = utc_now_iso()
    ch = list(row["adaptive_changes"])
    ch.append({"ts": ts, "change": (change or "")[:2000], "context": dict(context or {})})
    row["adaptive_changes"] = ch[-500:]
    row["updated_at"] = ts
    _planning_records(st)[str(planning_id)] = row
    try:
        from app.runtime.events.runtime_events import emit_runtime_event

        emit_runtime_event(st, "adaptive_change_recorded", planning_id=str(planning_id), change=change[:200])
    except Exception:
        pass


def append_retry_strategy_record(
    st: dict[str, Any],
    planning_id: str,
    *,
    strategy: str,
    reason: str,
    retry_count: int,
    next_retry_at: float | None,
    max_retries: int,
    adapted: bool = False,
) -> None:
    row = _get_planning(st, str(planning_id))
    if not row:
        return
    ensure_adaptive_planning_fields(row)
    ts = utc_now_iso()
    hist = list(row["retry_strategy_history"])
    hist.append(
        {
            "ts": ts,
            "strategy": str(strategy)[:120],
            "reason": (reason or "")[:2000],
            "retry_count": int(retry_count),
            "next_retry_at": next_retry_at,
            "max_retries": int(max_retries),
            "adapted": bool(adapted),
        }
    )
    row["retry_strategy_history"] = hist[-500:]
    row["updated_at"] = ts
    _planning_records(st)[str(planning_id)] = row
    try:
        from app.runtime.events.runtime_events import emit_runtime_event

        emit_runtime_event(
            st,
            "retry_strategy_recorded",
            planning_id=str(planning_id),
            retry_count=int(retry_count),
            strategy=str(strategy)[:120],
        )
    except Exception:
        pass


def append_delegation_decision(st: dict[str, Any], planning_id: str, payload: dict[str, Any]) -> None:
    row = _get_planning(st, str(planning_id))
    if not row:
        return
    ensure_adaptive_planning_fields(row)
    ts = utc_now_iso()
    ent = dict(payload)
    ent.setdefault("ts", ts)
    dec = list(row["delegation_decisions"])
    dec.append(ent)
    row["delegation_decisions"] = dec[-500:]
    row["updated_at"] = ts
    _planning_records(st)[str(planning_id)] = row
    try:
        from app.runtime.events.runtime_events import emit_runtime_event

        emit_runtime_event(st, "delegation_decision_recorded", planning_id=str(planning_id))
    except Exception:
        pass


def bump_execution_quality(st: dict[str, Any], planning_id: str, *, outcome: str) -> None:
    row = _get_planning(st, str(planning_id))
    if not row:
        return
    ensure_adaptive_planning_fields(row)
    eq = dict(row.get("execution_quality") or {})
    eq["attempts"] = int(eq.get("attempts") or 0) + 1
    if outcome == "success":
        eq["successes"] = int(eq.get("successes") or 0) + 1
    elif outcome == "failure":
        eq["failures"] = int(eq.get("failures") or 0) + 1
    row["execution_quality"] = eq
    row["updated_at"] = utc_now_iso()
    _planning_records(st)[str(planning_id)] = row
