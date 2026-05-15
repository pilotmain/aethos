# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control JSON snapshot slice for ``aethos.json`` orchestration (OpenClaw parity)."""

from __future__ import annotations

from typing import Any

from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state
from app.runtime.sessions.session_registry import list_sessions_for_user


def build_orchestration_runtime_snapshot(user_id: str | None) -> dict[str, Any]:
    """Read-only view for Mission Control ``/state`` (no UI redesign — data only)."""
    uid = (user_id or "").strip()
    st = load_runtime_state()
    metrics = dict(st.get("runtime_metrics") or {}) if isinstance(st.get("runtime_metrics"), dict) else {}
    gw = dict(st.get("gateway") or {}) if isinstance(st.get("gateway"), dict) else {}
    sch = {}
    orch = st.get("orchestration")
    if isinstance(orch, dict) and isinstance(orch.get("scheduler"), dict):
        sch = dict(orch["scheduler"])

    sessions_out: list[dict[str, Any]] = []
    if uid:
        sessions_out = list_sessions_for_user(st, uid)

    tasks_out: list[dict[str, Any]] = []
    wf_active = wf_done = wf_fail = 0
    active_tasks = retrying_tasks = queued_tasks = 0
    for tid, t in task_registry.registry(st).items():
        if not isinstance(t, dict):
            continue
        if uid and str(t.get("user_id") or "") != uid:
            continue
        stt = str(t.get("state") or "")
        if stt in ("queued", "scheduled"):
            queued_tasks += 1
        if stt == "running":
            active_tasks += 1
        if stt == "retrying":
            retrying_tasks += 1
        if str(t.get("type") or "") == "workflow":
            if stt in ("queued", "scheduled", "running", "waiting", "retrying", "recovering"):
                wf_active += 1
            elif stt == "completed":
                wf_done += 1
            elif stt == "failed":
                wf_fail += 1
        if uid:
            tasks_out.append(
                {
                    "task_id": str(tid),
                    "state": stt,
                    "type": t.get("type"),
                    "execution_plan_id": t.get("execution_plan_id"),
                    "owner_session_id": t.get("owner_session_id"),
                    "owner_user_id": t.get("owner_user_id"),
                    "assigned_agent_id": t.get("assigned_agent_id"),
                    "updated_at": t.get("updated_at"),
                }
            )

    queue_depths = {qn: task_queue.queue_len(st, qn) for qn in task_queue.QUEUE_NAMES}

    plans_n = 0
    ex = st.get("execution")
    if isinstance(ex, dict) and isinstance(ex.get("plans"), dict):
        plans_n = len(ex["plans"])

    buf = st.get("runtime_event_buffer")
    event_tail = list(buf[-80:]) if isinstance(buf, list) else []

    return {
        "heartbeat": {
            "gateway_running": bool(gw.get("running")),
            "last_heartbeat": gw.get("last_heartbeat"),
            "scheduler_ticks": sch.get("ticks"),
            "scheduler_last_tick": sch.get("last_tick"),
            "scheduler_running": bool(sch.get("running")),
        },
        "queues": queue_depths,
        "metrics": metrics,
        "execution_graph_count": plans_n,
        "workflows": {"active": wf_active, "completed": wf_done, "failed": wf_fail},
        "tasks": {
            "active": active_tasks,
            "queued": queued_tasks,
            "retrying": retrying_tasks,
            "sample": tasks_out[:40],
        },
        "sessions": sessions_out[:40],
        "runtime_events_tail": event_tail,
    }
