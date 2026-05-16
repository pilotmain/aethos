# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Persistent planning rows keyed by ``planning_id``."""

from __future__ import annotations

import uuid
from typing import Any

from app.planning import planning_events
from app.planning.adaptive_planning_row import ensure_adaptive_planning_fields
from app.runtime.runtime_state import utc_now_iso


def planning_records(st: dict[str, Any]) -> dict[str, Any]:
    pr = st.setdefault("planning_records", {})
    if not isinstance(pr, dict):
        st["planning_records"] = {}
        return st["planning_records"]
    return pr


def outcomes_list(st: dict[str, Any]) -> list[Any]:
    o = st.setdefault("planning_outcomes", [])
    if not isinstance(o, list):
        st["planning_outcomes"] = []
        return st["planning_outcomes"]
    return o


def _bump(st: dict[str, Any], key: str) -> None:
    m = st.setdefault("runtime_metrics", {})
    if not isinstance(m, dict):
        st["runtime_metrics"] = {}
        m = st["runtime_metrics"]
    m[key] = int(m.get(key) or 0) + 1


def ensure_planning_record_for_plan(
    st: dict[str, Any],
    *,
    task_id: str,
    plan_id: str,
    user_id: str,
) -> str:
    """Create or refresh a planning record bound to an execution plan (idempotent by plan_id)."""
    pid = str(plan_id)
    existing_id: str | None = None
    for plid, row in planning_records(st).items():
        if isinstance(row, dict) and str(row.get("plan_id") or "") == pid:
            existing_id = str(plid)
            break
    if existing_id:
        planning_records(st)[existing_id]["updated_at"] = utc_now_iso()
        ensure_adaptive_planning_fields(planning_records(st)[existing_id])
        return existing_id
    plnid = f"pln_{uuid.uuid4().hex[:12]}"
    ts = utc_now_iso()
    planning_records(st)[plnid] = {
        "planning_id": plnid,
        "task_id": str(task_id),
        "plan_id": pid,
        "user_id": str(user_id),
        "status": "active",
        "created_at": ts,
        "updated_at": ts,
        "reasoning_state": {"notes": []},
        "execution_strategy": {"mode": "default", "priority": "balanced"},
        "optimization_state": {"last_score": None},
        "recovery_plan": {},
        "delegation_plan": {},
    }
    _bump(st, "planning_generated_total")
    planning_events.emit_planning_event(
        st, "plan_generated", planning_id=plnid, task_id=str(task_id), plan_id=pid, user_id=str(user_id)
    )
    ensure_adaptive_planning_fields(planning_records(st)[plnid])
    return plnid


def get_planning(st: dict[str, Any], planning_id: str) -> dict[str, Any] | None:
    row = planning_records(st).get(str(planning_id))
    return row if isinstance(row, dict) else None


def list_planning_for_user(st: dict[str, Any], user_id: str) -> list[dict[str, Any]]:
    uid = str(user_id or "").strip()
    out: list[dict[str, Any]] = []
    for _pid, row in planning_records(st).items():
        if not isinstance(row, dict):
            continue
        if uid and str(row.get("user_id") or "") != uid:
            continue
        out.append(dict(row))
    out.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    return out


def recover_planning_on_boot(st: dict[str, Any]) -> dict[str, Any]:
    n = 0
    ts = utc_now_iso()
    for plnid, row in list(planning_records(st).items()):
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "") != "active":
            continue
        row["status"] = "restored"
        row["updated_at"] = ts
        row.setdefault("recovery_plan", {})["boot"] = ts
        planning_records(st)[str(plnid)] = row
        n += 1
    return {"planning_records_restored": n}
