# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Heuristic delegation target selection using coordination agent load."""

from __future__ import annotations

from typing import Any

from app.agents.agent_registry import agents_map
from app.orchestration import task_queue
from app.planning import planning_events


def pick_child_agent_for_task(st: dict[str, Any], *, user_id: str, exclude: str | None = None) -> str | None:
    uid = str(user_id or "").strip()
    best: str | None = None
    best_load = 1 << 30
    for aid, ag in agents_map(st).items():
        if not isinstance(ag, dict):
            continue
        if uid and str(ag.get("user_id") or "") != uid:
            continue
        if exclude and str(aid) == str(exclude):
            continue
        load = len(ag.get("active_tasks") or []) + len(ag.get("delegated_tasks") or [])
        qd = sum(task_queue.queue_len(st, qn) for qn in task_queue.QUEUE_NAMES)
        score = load * 10 + qd
        if score < best_load:
            best_load = score
            best = str(aid)
    if best:
        planning_events.emit_planning_event(
            st, "delegation_optimized", child_agent_id=best, user_id=uid, score=best_load
        )
    return best
