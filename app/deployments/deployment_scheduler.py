# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lightweight in-state scheduler hooks (priority queue + per-environment locks)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import utc_now_iso


def scheduler_root(st: dict[str, Any]) -> dict[str, Any]:
    s = st.setdefault("deployment_scheduler", {})
    if not isinstance(s, dict):
        st["deployment_scheduler"] = {"pending": [], "locks": {}}
        return st["deployment_scheduler"]
    s.setdefault("pending", [])
    s.setdefault("locks", {})
    if not isinstance(s["pending"], list):
        s["pending"] = []
    if not isinstance(s["locks"], dict):
        s["locks"] = {}
    return s


def enqueue_deployment(st: dict[str, Any], deployment_id: str, *, priority: int = 0) -> None:
    root = scheduler_root(st)
    pending = root["pending"]
    assert isinstance(pending, list)
    pending.append({"deployment_id": str(deployment_id), "priority": int(priority), "enqueued_at": utc_now_iso()})
    pending.sort(key=lambda x: (-int(x.get("priority") or 0), str(x.get("enqueued_at") or "")))


def acquire_environment_lock(st: dict[str, Any], environment_id: str, holder: str) -> bool:
    locks = scheduler_root(st)["locks"]
    assert isinstance(locks, dict)
    eid = str(environment_id)
    cur = locks.get(eid)
    if cur and str(cur) != str(holder):
        return False
    locks[eid] = str(holder)
    return True


def release_environment_lock(st: dict[str, Any], environment_id: str, holder: str) -> None:
    locks = scheduler_root(st)["locks"]
    assert isinstance(locks, dict)
    eid = str(environment_id)
    if str(locks.get(eid) or "") == str(holder):
        locks.pop(eid, None)
