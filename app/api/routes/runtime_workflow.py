"""Runtime workflow + multi-session operational APIs (OpenClaw parity — ``/api/v1/runtime/*``)."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from app.core.paths import get_aethos_home_dir
from app.core.security import get_valid_web_user_id
from app.execution import execution_memory
from app.execution import execution_plan
from app.execution import workflow_recovery
from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state
from app.runtime.sessions.session_registry import get_session, list_sessions_for_user
from app.services.events.bus import subscribe, unsubscribe

router = APIRouter(prefix="/runtime", tags=["runtime-workflow"])


def _task_belongs(t: dict[str, Any], app_user_id: str) -> bool:
    return str(t.get("user_id") or "") == app_user_id


def _session_belongs(row: dict[str, Any], app_user_id: str) -> bool:
    return str(row.get("user_id") or "") == app_user_id


def _artifacts_from_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in plan.get("steps") or []:
        if not isinstance(s, dict):
            continue
        sid = str(s.get("step_id") or "")
        res = s.get("result") if isinstance(s.get("result"), dict) else {}
        if res.get("stdout"):
            out.append({"step_id": sid, "kind": "stdout", "preview": str(res.get("stdout"))[:4000]})
        if res.get("stderr"):
            out.append({"step_id": sid, "kind": "stderr", "preview": str(res.get("stderr"))[:2000]})
        if res.get("path") and res.get("tool") in ("file_read", "file_write", "file_patch"):
            out.append({"step_id": sid, "kind": "file", "path": res.get("path"), "tool": res.get("tool")})
    return out


@router.get("/tasks")
def list_runtime_tasks(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    items: list[dict[str, Any]] = []
    for tid, t in task_registry.registry(st).items():
        if not isinstance(t, dict) or not _task_belongs(t, app_user_id):
            continue
        items.append(
            {
                "task_id": str(tid),
                "state": t.get("state"),
                "type": t.get("type"),
                "execution_plan_id": t.get("execution_plan_id"),
                "owner_session_id": t.get("owner_session_id"),
                "owner_user_id": t.get("owner_user_id"),
                "assigned_agent_id": t.get("assigned_agent_id"),
                "created_at": t.get("created_at"),
                "updated_at": t.get("updated_at"),
            }
        )
    return {"tasks": items, "count": len(items)}


@router.get("/tasks/{task_id}")
def get_runtime_task(
    task_id: str,
    full: bool = Query(False, description="Include memory, checkpoints, artifact index"),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    st = load_runtime_state()
    t = task_registry.get_task(st, task_id)
    if not t or not _task_belongs(t, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    pid = t.get("execution_plan_id")
    plan = execution_plan.get_plan(st, str(pid)) if pid else None
    out: dict[str, Any] = {"task": dict(t), "plan": plan}
    if full and pid:
        ex = execution_plan.execution_root(st)
        cpx = (ex.get("checkpoints") or {}).get(str(pid)) or {}
        out["checkpoints"] = cpx if isinstance(cpx, dict) else {}
        out["execution_memory"] = execution_memory.get_memory(st, task_id)
        out["artifacts_index"] = _artifacts_from_plan(plan or {})
    return out


@router.get("/tasks/{task_id}/result")
def get_runtime_task_result(task_id: str, app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    t = task_registry.get_task(st, task_id)
    if not t or not _task_belongs(t, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    pid = t.get("execution_plan_id")
    if not pid:
        return {"task_id": task_id, "plan_id": None, "steps": []}
    plan = execution_plan.get_plan(st, str(pid))
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Plan not found")
    steps_out: list[dict[str, Any]] = []
    for s in plan.get("steps") or []:
        if not isinstance(s, dict):
            continue
        steps_out.append(
            {
                "step_id": s.get("step_id"),
                "status": s.get("status"),
                "type": s.get("type"),
                "result": s.get("result"),
                "error": s.get("error"),
            }
        )
    return {"task_id": task_id, "plan_id": str(pid), "task_state": t.get("state"), "steps": steps_out}


@router.get("/tasks/{task_id}/artifacts")
def get_runtime_task_artifacts(task_id: str, app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    t = task_registry.get_task(st, task_id)
    if not t or not _task_belongs(t, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    pid = t.get("execution_plan_id")
    if not pid:
        return {"task_id": task_id, "artifacts": []}
    plan = execution_plan.get_plan(st, str(pid))
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return {"task_id": task_id, "plan_id": str(pid), "artifacts": _artifacts_from_plan(plan)}


@router.get("/tasks/{task_id}/logs")
def get_runtime_task_logs(
    task_id: str,
    lines: int = Query(120, ge=1, le=2000),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    st = load_runtime_state()
    t = task_registry.get_task(st, task_id)
    if not t or not _task_belongs(t, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    tid = str(task_id)
    hits: list[str] = []
    for stem in ("tools", "workflows", "execution", "orchestration"):
        p = get_aethos_home_dir() / "logs" / f"{stem}.log"
        if not p.is_file():
            continue
        try:
            for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
                if tid in ln:
                    hits.append(f"{stem}:{ln}")
        except OSError:
            continue
    return {"task_id": tid, "lines": hits[-lines:]}


@router.get("/artifacts")
def list_runtime_artifacts(
    app_user_id: str = Depends(get_valid_web_user_id),
    limit: int = Query(40, ge=1, le=200),
) -> dict[str, Any]:
    st = load_runtime_state()
    arts: list[dict[str, Any]] = []
    for tid, t in task_registry.registry(st).items():
        if not isinstance(t, dict) or not _task_belongs(t, app_user_id):
            continue
        pid = t.get("execution_plan_id")
        if not pid:
            continue
        plan = execution_plan.get_plan(st, str(pid))
        if not plan:
            continue
        for a in _artifacts_from_plan(plan):
            arts.append({"task_id": str(tid), "plan_id": str(pid), **a})
            if len(arts) >= limit:
                return {"artifacts": arts, "count": len(arts)}
    return {"artifacts": arts, "count": len(arts)}


@router.get("/plans/{plan_id}")
def get_runtime_plan(plan_id: str, app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    plan = execution_plan.get_plan(st, plan_id)
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Plan not found")
    tid = str(plan.get("task_id") or "")
    t = task_registry.get_task(st, tid)
    if not t or not _task_belongs(t, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return {"plan": plan}


@router.get("/summary")
def runtime_workflow_summary(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    active = 0
    done = 0
    failed = 0
    latest_tid: str | None = None
    latest_pid: str | None = None
    latest_updated = ""
    for tid, t in task_registry.registry(st).items():
        if not isinstance(t, dict) or str(t.get("type") or "") != "workflow":
            continue
        if not _task_belongs(t, app_user_id):
            continue
        stt = str(t.get("state") or "")
        if stt in ("queued", "scheduled", "running", "waiting", "retrying", "recovering"):
            active += 1
        elif stt == "completed":
            done += 1
        elif stt == "failed":
            failed += 1
        upd = str(t.get("updated_at") or t.get("created_at") or "")
        if upd >= latest_updated:
            latest_updated = upd
            latest_tid = str(tid)
            latest_pid = str(t.get("execution_plan_id") or "") or None
    rep = workflow_recovery.workflow_integrity_report(st)
    return {
        "workflows": {"active": active, "completed": done, "failed": failed},
        "latest_task_id": latest_tid,
        "latest_plan_id": latest_pid,
        "integrity": rep,
    }


@router.get("/sessions")
def list_runtime_sessions(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    rows = list_sessions_for_user(st, app_user_id)
    return {"sessions": rows, "count": len(rows)}


@router.get("/sessions/{session_id}")
def get_runtime_session(session_id: str, app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    row = get_session(st, session_id)
    if not row or not _session_belongs(row, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Session not found")
    return {"session": row}


@router.get("/events")
def list_runtime_events(
    app_user_id: str = Depends(get_valid_web_user_id),
    limit: int = Query(80, ge=1, le=500),
) -> dict[str, Any]:
    st = load_runtime_state()
    buf = st.get("runtime_event_buffer")
    if not isinstance(buf, list):
        return {"events": [], "count": 0}
    scoped = [e for e in buf if isinstance(e, dict) and str(e.get("user_id") or "") == app_user_id]
    tail = scoped[-limit:]
    return {"events": tail, "count": len(tail)}


@router.get("/metrics")
def get_runtime_metrics(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    m = dict(st.get("runtime_metrics") or {}) if isinstance(st.get("runtime_metrics"), dict) else {}
    queues = {qn: task_queue.queue_len(st, qn) for qn in task_queue.QUEUE_NAMES}
    sess_n = 0
    rs = st.get("runtime_sessions")
    if isinstance(rs, dict):
        sess_n = len(rs)
    from app.deployments.deployment_health import deployment_health_summary, environment_health_bridge

    dep_h = deployment_health_summary(st, user_id=app_user_id)
    env_h = environment_health_bridge(st, user_id=app_user_id)
    return {
        "metrics": m,
        "queues": queues,
        "session_count": sess_n,
        "deployment_health": dep_h,
        "environment_health": env_h,
    }


@router.get("/queues")
def get_runtime_queues(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    _ = app_user_id
    st = load_runtime_state()
    return {qn: task_queue.queue_len(st, qn) for qn in task_queue.QUEUE_NAMES}


@router.get("/supervisors")
def list_runtime_supervisors(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    rs = st.get("runtime_supervisors")
    rows: list[dict[str, Any]] = []
    if isinstance(rs, dict):
        for row in rs.values():
            if not isinstance(row, dict):
                continue
            if str(row.get("user_id") or "") and str(row.get("user_id") or "") != str(app_user_id):
                continue
            rows.append(dict(row))
    return {"supervisors": rows, "count": len(rows)}


@router.get("/loops")
def list_autonomous_loops(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    lo = st.get("autonomous_loops")
    rows: list[dict[str, Any]] = []
    if isinstance(lo, list):
        for row in lo:
            if not isinstance(row, dict):
                continue
            if str(row.get("user_id") or "") and str(row.get("user_id") or "") != str(app_user_id):
                continue
            rows.append(dict(row))
    return {"loops": rows, "count": len(rows)}


@router.get("/planning")
def list_planning_runtime(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    from app.planning.planner_runtime import list_planning_for_user

    rows = list_planning_for_user(st, app_user_id)
    return {"planning": rows, "count": len(rows)}


@router.get("/planning/{planning_id}")
def get_planning_runtime(planning_id: str, app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    from app.planning.planner_runtime import get_planning

    row = get_planning(st, planning_id)
    if not row or str(row.get("user_id") or "") != str(app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="unknown planning_id")
    return {"planning": row}


@router.get("/reasoning")
def list_reasoning_runtime(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    from app.planning.planner_runtime import list_planning_for_user

    rows = list_planning_for_user(st, app_user_id)
    out = [
        {
            "planning_id": r.get("planning_id"),
            "task_id": r.get("task_id"),
            "plan_id": r.get("plan_id"),
            "reasoning_state": r.get("reasoning_state"),
        }
        for r in rows
    ]
    return {"reasoning": out, "count": len(out)}


@router.get("/optimization")
def get_optimization_runtime(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    m = dict(st.get("runtime_metrics") or {}) if isinstance(st.get("runtime_metrics"), dict) else {}
    from app.planning.planner_runtime import list_planning_for_user

    rows = list_planning_for_user(st, app_user_id)
    samples = [
        {"planning_id": r.get("planning_id"), "optimization_state": r.get("optimization_state")}
        for r in rows[:50]
    ]
    return {
        "metrics": {
            "optimization_cycles_total": int(m.get("optimization_cycles_total") or 0),
            "optimization_success_total": int(m.get("optimization_success_total") or 0),
        },
        "planning_samples": samples,
    }


@router.get("/replanning")
def get_replanning_runtime(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    tr = task_registry.registry(st)
    ol = st.get("planning_outcomes")
    tail: list[dict[str, Any]] = []
    if isinstance(ol, list):
        for snap in ol[-120:]:
            if not isinstance(snap, dict):
                continue
            tid = str(snap.get("task_id") or "")
            t = tr.get(tid) if tid else None
            if isinstance(t, dict) and str(t.get("user_id") or "") == str(app_user_id):
                tail.append(dict(snap))
    m = dict(st.get("runtime_metrics") or {}) if isinstance(st.get("runtime_metrics"), dict) else {}
    return {
        "outcomes_tail": tail[-40:],
        "replanning_total": int(m.get("replanning_total") or 0),
        "adaptive_retry_total": int(m.get("adaptive_retry_total") or 0),
    }


@router.get("/health")
def get_runtime_health(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    gw = dict(st.get("gateway") or {}) if isinstance(st.get("gateway"), dict) else {}
    sch = {}
    orch = st.get("orchestration")
    if isinstance(orch, dict) and isinstance(orch.get("scheduler"), dict):
        sch = dict(orch["scheduler"])
    buf = st.get("runtime_event_buffer")
    ev_ok = isinstance(buf, list)
    ev_len = len(buf) if ev_ok else 0
    from app.deployments.deployment_health import deployment_health_summary, environment_health_bridge

    dep_h = deployment_health_summary(st, user_id=app_user_id)
    env_h = environment_health_bridge(st, user_id=app_user_id)
    ow = st.get("operational_workflows")
    ow_n = len(ow) if isinstance(ow, list) else 0
    ds = st.get("deployment_scheduler")
    ds_p = len(ds.get("pending") or []) if isinstance(ds, dict) and isinstance(ds.get("pending"), list) else 0
    from app.runtime.integrity.runtime_integrity import validate_runtime_state

    inv = validate_runtime_state(st)
    rec = st.get("recovery") or {}
    rec_events = rec.get("events") if isinstance(rec, dict) else None
    rec_n = len(rec_events) if isinstance(rec_events, list) else 0
    from app.agents.agent_delegation import delegations_map
    from app.agents.agent_registry import list_agents_for_user

    agents_u = list_agents_for_user(st, app_user_id)
    del_n = sum(
        1
        for d in delegations_map(st).values()
        if isinstance(d, dict) and str(d.get("user_id") or "") == str(app_user_id)
    )
    lo2 = st.get("autonomous_loops") if isinstance(st.get("autonomous_loops"), list) else []
    loops_run = sum(
        1
        for x in lo2
        if isinstance(x, dict)
        and str(x.get("user_id") or "") == str(app_user_id)
        and str(x.get("status")) == "running"
    )
    supm = st.get("runtime_supervisors") if isinstance(st.get("runtime_supervisors"), dict) else {}
    sup_n = sum(
        1 for x in supm.values() if isinstance(x, dict) and str(x.get("user_id") or "") == str(app_user_id)
    )
    from app.planning.planner_runtime import list_planning_for_user

    pr_rows = list_planning_for_user(st, app_user_id)
    rm = st.get("runtime_metrics") if isinstance(st.get("runtime_metrics"), dict) else {}
    planning_block = {
        "records": len(pr_rows),
        "planning_generated_total": int(rm.get("planning_generated_total") or 0),
        "replanning_total": int(rm.get("replanning_total") or 0),
        "optimization_cycles_total": int(rm.get("optimization_cycles_total") or 0),
        "adaptive_retry_total": int(rm.get("adaptive_retry_total") or 0),
        "reasoning_cycles_total": int(rm.get("reasoning_cycles_total") or 0),
    }
    return {
        "gateway_running": bool(gw.get("running")),
        "scheduler_running": bool(sch.get("running")),
        "scheduler_ticks": sch.get("ticks"),
        "scheduler_last_error": sch.get("last_error"),
        "runtime_event_buffer_ok": ev_ok,
        "runtime_event_buffer_size": ev_len,
        "recovery_events": rec_n,
        "integrity_ok": bool(inv.get("ok")),
        "integrity_issue_count": int(inv.get("issue_count") or 0),
        "workspace_root": str((st.get("workspace") or {}).get("root") or ""),
        "deployment_health": dep_h,
        "environment_health": env_h,
        "operational_workflows_count": ow_n,
        "deployment_scheduler_pending": ds_p,
        "coordination": {
            "agents": len(agents_u),
            "delegations": del_n,
            "loops_running": loops_run,
            "supervisors": sup_n,
        },
        "planning": planning_block,
    }


@router.get("/integrity")
def get_runtime_integrity(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    _ = app_user_id
    st = load_runtime_state()
    from app.runtime.integrity.runtime_integrity import validate_runtime_state

    return validate_runtime_state(st)


@router.get("/logs")
def tail_runtime_logs(
    stem: str = Query("tools", description="tools | workflows | execution | orchestration | …"),
    lines: int = Query(40, ge=1, le=500),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ = app_user_id
    allowed = {
        "tools",
        "workflows",
        "execution",
        "orchestration",
        "runtime",
        "recovery",
        "runtime_events",
        "runtime_sessions",
        "runtime_metrics",
        "deployments",
        "deployment_health",
        "deployment_recovery",
        "environments",
        "rollback",
        "operations",
        "agents",
        "agent_supervisor",
        "agent_delegation",
        "autonomous_loops",
        "runtime_supervision",
        "planning",
        "reasoning",
        "optimization",
        "replanning",
        "adaptive_execution",
        "delegation_optimization",
    }
    if stem not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"stem must be one of {sorted(allowed)}")
    path = get_aethos_home_dir() / "logs" / f"{stem}.log"
    if not path.is_file():
        return {"stem": stem, "lines": []}
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {"stem": stem, "lines": []}
    tail = raw[-lines:]
    return {"stem": stem, "path": str(path), "lines": tail}


@router.websocket("/events/ws")
async def runtime_events_websocket(ws: WebSocket, user_id: str | None = Query(None)) -> None:
    """Live bus stream filtered to ``user_id`` query (matches ``X-User-Id`` in HTTP tests)."""
    await ws.accept()
    uid = (user_id or "").strip()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=500)
    loop = asyncio.get_running_loop()

    def push(event: dict[str, Any]) -> None:
        if uid:
            pl = event.get("payload")
            if not isinstance(pl, dict) or str(pl.get("user_id") or "") != uid:
                return

        def _enqueue() -> None:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        try:
            loop.call_soon_threadsafe(_enqueue)
        except RuntimeError:
            pass

    subscribe(push)

    async def pump() -> None:
        while True:
            ev = await queue.get()
            await ws.send_json(ev)

    pump_task = asyncio.create_task(pump())
    try:
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
    finally:
        pump_task.cancel()
        try:
            await pump_task
        except asyncio.CancelledError:
            pass
        unsubscribe(push)
