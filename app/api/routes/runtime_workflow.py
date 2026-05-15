"""Read-only runtime workflow inspection (OpenClaw parity — ``/api/v1/runtime/*``)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.paths import get_aethos_home_dir
from app.core.security import get_valid_web_user_id
from app.execution import execution_plan
from app.execution import workflow_recovery
from app.orchestration import task_registry
from app.runtime.runtime_state import load_runtime_state

router = APIRouter(prefix="/runtime", tags=["runtime-workflow"])


def _task_belongs(t: dict[str, Any], app_user_id: str) -> bool:
    return str(t.get("user_id") or "") == app_user_id


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
                "created_at": t.get("created_at"),
                "updated_at": t.get("updated_at"),
            }
        )
    return {"tasks": items, "count": len(items)}


@router.get("/tasks/{task_id}")
def get_runtime_task(task_id: str, app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    t = task_registry.get_task(st, task_id)
    if not t or not _task_belongs(t, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    pid = t.get("execution_plan_id")
    plan = execution_plan.get_plan(st, str(pid)) if pid else None
    return {"task": dict(t), "plan": plan}


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


@router.get("/logs")
def tail_runtime_logs(
    stem: str = Query("tools", description="tools | workflows | execution | orchestration"),
    lines: int = Query(40, ge=1, le=500),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _ = app_user_id
    allowed = {"tools", "workflows", "execution", "orchestration", "runtime", "recovery"}
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
