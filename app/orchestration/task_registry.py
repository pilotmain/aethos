"""Persistent task registry (``task_registry`` in ``aethos.json``)."""

from __future__ import annotations

import time
import uuid
from typing import Any

TASK_STATES = frozenset(
    {
        "queued",
        "scheduled",
        "running",
        "waiting",
        "blocked",
        "retrying",
        "completed",
        "failed",
        "cancelled",
        "recovering",
    }
)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def registry(st: dict[str, Any]) -> dict[str, Any]:
    tr = st.setdefault("task_registry", {})
    if not isinstance(tr, dict):
        st["task_registry"] = {}
        return st["task_registry"]
    return tr


def put_task(st: dict[str, Any], task: dict[str, Any]) -> str:
    tid = str(task.get("id") or uuid.uuid4())
    task = dict(task)
    task["id"] = tid
    task.setdefault("created_at", _now_iso())
    task["updated_at"] = _now_iso()
    state = str(task.get("state") or "queued")
    if state not in TASK_STATES:
        state = "queued"
    task["state"] = state
    registry(st)[tid] = task
    return tid


def get_task(st: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    t = registry(st).get(task_id)
    return t if isinstance(t, dict) else None


def update_task_state(st: dict[str, Any], task_id: str, state: str, **extra: Any) -> None:
    t = get_task(st, task_id)
    if not t:
        return
    if state in TASK_STATES:
        t["state"] = state
    t["updated_at"] = _now_iso()
    for k, v in extra.items():
        t[k] = v


def count_by_states(st: dict[str, Any], states: set[str]) -> int:
    n = 0
    for t in registry(st).values():
        if isinstance(t, dict) and str(t.get("state")) in states:
            n += 1
    return n


def list_task_ids_by_state(st: dict[str, Any], state: str) -> list[str]:
    out: list[str] = []
    for tid, t in registry(st).items():
        if isinstance(t, dict) and str(t.get("state")) == state:
            out.append(str(tid))
    return out
