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
                    "assigned_coordination_agent_id": t.get("assigned_coordination_agent_id"),
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
        "deployments": _deployments_slice(st, uid),
        "environments": _environments_slice(st, uid),
        "operational_workflows_tail": _ops_tail(st),
        "deployment_scheduler": _dsched_lens(st),
        "coordination_agents": _coord_agents_slice(st, uid),
        "agent_delegations_tail": _delegations_tail(st, uid),
        "autonomous_loops_tail": _loops_tail(st, uid),
        "runtime_supervisors": _supervisors_slice(st, uid),
        "planning": {
            "records_tail": _planning_records_tail(st, uid),
            "outcomes_tail": _planning_outcomes_tail(st, uid),
            "reasoning_tail": _planning_reasoning_tail(st, uid),
            "optimization_tail": _planning_optimization_tail(st, uid),
        },
        "resilience": _resilience_slice(st),
    }


def _resilience_slice(st: dict[str, Any]) -> dict[str, Any]:
    from app.runtime.backups.runtime_snapshots import list_runtime_backup_files
    from app.runtime.corruption.runtime_validation import scan_queue_duplicates_and_shape
    from app.runtime.integrity.runtime_integrity import validate_runtime_state

    m = st.get("runtime_metrics") if isinstance(st.get("runtime_metrics"), dict) else {}
    rs = st.get("runtime_resilience") if isinstance(st.get("runtime_resilience"), dict) else {}
    qc = st.get("runtime_corruption_quarantine")
    inv = validate_runtime_state(st)
    bk = list_runtime_backup_files(limit=200)
    sig = scan_queue_duplicates_and_shape(st)
    return {
        "integrity_ok": bool(inv.get("ok")),
        "integrity_issue_count": int(inv.get("issue_count") or 0),
        "queue_duplicate_entries_signal": int(sig.get("duplicate_queue_entries") or 0),
        "runtime_backups_total": int(m.get("runtime_backups_total") or 0),
        "backup_files_on_disk": len(bk),
        "quarantine_records": len(qc) if isinstance(qc, list) else 0,
        "last_cleanup": rs.get("last_cleanup"),
        "last_backup": rs.get("last_backup"),
    }


def _deployments_slice(st: dict[str, Any], uid: str) -> dict[str, Any]:
    from app.deployments.deployment_registry import list_deployments_for_user
    from app.environments import environment_locks

    if not uid:
        return {"sample": [], "count": 0, "environment_locks": []}
    rows = list_deployments_for_user(st, uid)
    sample: list[dict[str, Any]] = []
    for r in rows[:40]:
        if not isinstance(r, dict):
            continue
        hist = r.get("stage_history")
        hist_tail = list(hist[-12:]) if isinstance(hist, list) else []
        lg = r.get("logs")
        latest = lg[-1] if isinstance(lg, list) and lg else None
        arts = r.get("artifacts")
        ac = len(arts) if isinstance(arts, list) else 0
        sample.append(
            {
                "deployment_id": r.get("deployment_id"),
                "deployment_stage": r.get("deployment_stage"),
                "status": r.get("status"),
                "environment_id": r.get("environment_id"),
                "stage_history_tail": hist_tail,
                "rollback": r.get("rollback"),
                "artifacts_count": ac,
                "recovery": r.get("recovery"),
                "latest_log": latest,
                "failure_reason": r.get("failure_reason"),
            }
        )
    return {
        "sample": sample,
        "count": len(rows),
        "environment_locks": environment_locks.list_locks_for_user(st, uid)[:40],
    }


def _environments_slice(st: dict[str, Any], uid: str) -> dict[str, Any]:
    from app.environments import environment_registry

    if not uid:
        return {"sample": [], "count": 0}
    rows = environment_registry.list_environments_for_user(st, uid)
    return {"sample": rows[:40], "count": len(rows)}


def _ops_tail(st: dict[str, Any]) -> list[dict[str, Any]]:
    ow = st.get("operational_workflows")
    if not isinstance(ow, list):
        return []
    tail = [x for x in ow[-40:] if isinstance(x, dict)]
    return [dict(x) for x in tail]


def _dsched_lens(st: dict[str, Any]) -> dict[str, int]:
    ds = st.get("deployment_scheduler")
    if not isinstance(ds, dict):
        return {"pending": 0, "locks": 0}
    pend = ds.get("pending")
    locks = ds.get("locks")
    return {
        "pending": len(pend) if isinstance(pend, list) else 0,
        "locks": len(locks) if isinstance(locks, dict) else 0,
    }


def _coord_agents_slice(st: dict[str, Any], uid: str) -> dict[str, Any]:
    from app.agents.agent_health import effective_coordination_health
    from app.agents.agent_registry import list_agents_for_user

    if not uid:
        return {"sample": [], "count": 0, "coordination_health_counts": {}}
    rows = list_agents_for_user(st, uid)
    counts: dict[str, int] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        h = effective_coordination_health(r)
        counts[h] = counts.get(h, 0) + 1
    return {"sample": rows[:40], "count": len(rows), "coordination_health_counts": counts}


def _delegations_tail(st: dict[str, Any], uid: str) -> list[dict[str, Any]]:
    ad = st.get("agent_delegations")
    if not isinstance(ad, dict) or not uid:
        return []
    tail = [dict(v) for v in ad.values() if isinstance(v, dict) and str(v.get("user_id") or "") == uid]
    tail.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    return tail[:40]


def _loops_tail(st: dict[str, Any], uid: str) -> list[dict[str, Any]]:
    lo = st.get("autonomous_loops")
    if not isinstance(lo, list) or not uid:
        return []
    rows = [dict(x) for x in lo if isinstance(x, dict) and str(x.get("user_id") or "") == uid]
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""), reverse=True)
    return rows[-40:]


def _supervisors_slice(st: dict[str, Any], uid: str) -> dict[str, Any]:
    rs = st.get("runtime_supervisors")
    if not isinstance(rs, dict) or not uid:
        return {"sample": [], "count": 0}
    rows = [dict(v) for v in rs.values() if isinstance(v, dict) and str(v.get("user_id") or "") == uid]
    return {"sample": rows[:40], "count": len(rows)}


def _planning_records_tail(st: dict[str, Any], uid: str) -> list[dict[str, Any]]:
    from app.planning.planner_runtime import list_planning_for_user

    if not uid:
        return []
    return list_planning_for_user(st, uid)[:40]


def _planning_outcomes_tail(st: dict[str, Any], uid: str) -> list[dict[str, Any]]:
    if not uid:
        return []
    tr = task_registry.registry(st)
    ol = st.get("planning_outcomes")
    if not isinstance(ol, list):
        return []
    matched: list[dict[str, Any]] = []
    for snap in ol:
        if not isinstance(snap, dict):
            continue
        tid = str(snap.get("task_id") or "")
        t = tr.get(tid) if tid else None
        if isinstance(t, dict) and str(t.get("user_id") or "") == uid:
            matched.append(dict(snap))
    return matched[-40:]


def _planning_reasoning_tail(st: dict[str, Any], uid: str) -> list[dict[str, Any]]:
    from app.planning.planner_runtime import list_planning_for_user

    if not uid:
        return []
    out: list[dict[str, Any]] = []
    for row in list_planning_for_user(st, uid):
        plnid = row.get("planning_id")
        rs = row.get("reasoning_state")
        if not isinstance(rs, dict):
            continue
        notes = rs.get("notes")
        if not isinstance(notes, list):
            continue
        for n in notes[-12:]:
            if isinstance(n, dict):
                item = dict(n)
                item["planning_id"] = plnid
                out.append(item)
    return out[-40:]


def _planning_optimization_tail(st: dict[str, Any], uid: str) -> list[dict[str, Any]]:
    from app.planning.planner_runtime import list_planning_for_user

    if not uid:
        return []
    return [
        {"planning_id": r.get("planning_id"), "optimization_state": r.get("optimization_state")}
        for r in list_planning_for_user(st, uid)[:40]
    ]
