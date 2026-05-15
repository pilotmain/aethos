"""Supervisor: advance planned / chained autonomous execution one step at a time."""

from __future__ import annotations

import time
from typing import Any

from app.execution import execution_checkpoint
from app.execution import execution_dependencies
from app.execution import execution_log
from app.execution import execution_memory
from app.execution import execution_plan
from app.execution import execution_retry
from app.orchestration import orchestration_log
from app.orchestration import task_registry


def _reconcile_blocked_labels(plan: dict[str, Any]) -> None:
    for s in plan.get("steps") or []:
        if not isinstance(s, dict):
            continue
        stname = str(s.get("status") or "")
        if stname == "queued" and not execution_dependencies.dependencies_satisfied(plan, s):
            s["status"] = "blocked"
        elif stname == "blocked" and execution_dependencies.dependencies_satisfied(plan, s):
            s["status"] = "queued"


def _note_supervisor(st: dict[str, Any], *, error: str | None = None) -> None:
    sup = execution_plan.execution_root(st).setdefault("supervisor", {})
    if not isinstance(sup, dict):
        execution_plan.execution_root(st)["supervisor"] = {}
        sup = execution_plan.execution_root(st)["supervisor"]
    sup["ticks"] = int(sup.get("ticks") or 0) + 1
    sup["last_tick"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    sup["last_error"] = error
    execution_log.log_scheduler_event("execution_supervisor_tick", ticks=sup["ticks"])


def tick_planned_task(
    st: dict[str, Any],
    task_id: str,
    *,
    now_ts: float | None = None,
    source_queue: str | None = None,
) -> dict[str, Any] | None:
    """
    If ``task_id`` has an ``execution_plan_id``, run at most one plan step.
    Returns a result dict with ``terminal`` task-level state, or ``None`` if this task is not plan-driven.
    """
    t = task_registry.get_task(st, task_id)
    if not t:
        return None
    pid = t.get("execution_plan_id")
    if not pid:
        return None
    plan = execution_plan.get_plan(st, str(pid))
    if not plan:
        task_registry.update_task_state(st, task_id, "failed", reason="missing_execution_plan")
        _note_supervisor(st, error="missing_plan")
        return {"terminal": "failed", "plan_id": str(pid), "reason": "missing_plan"}

    if not execution_dependencies.validate_plan_dependency_dag(plan):
        task_registry.update_task_state(st, task_id, "failed", reason="invalid_dependency_dag")
        _note_supervisor(st, error="dependency_cycle")
        return {"terminal": "failed", "plan_id": str(pid), "reason": "dependency_cycle"}

    _reconcile_blocked_labels(plan)
    _note_supervisor(st)

    if execution_plan.any_step_failed(plan):
        task_registry.update_task_state(st, task_id, "failed")
        execution_plan.update_plan_timestamp(plan)
        plan["status"] = "failed"
        execution_log.log_execution_event(
            "execution_failed", task_id=task_id, plan_id=str(pid), status="failed"
        )
        return {"terminal": "failed", "plan_id": str(pid)}

    if execution_plan.all_steps_terminal(plan):
        task_registry.update_task_state(st, task_id, "completed")
        plan["status"] = "completed"
        execution_plan.update_plan_timestamp(plan)
        t2 = task_registry.get_task(st, task_id) or {}
        if str(t2.get("type") or "") == "deploy":
            deps = st.setdefault("deployments", [])
            if isinstance(deps, list):
                deps.append(
                    {
                        "task_id": task_id,
                        "plan_id": str(pid),
                        "status": "completed",
                        "stage": plan.get("deployment_stage"),
                        "recovered": bool((plan.get("deployment_recovery") or {}).get("resumed")),
                    }
                )
            orchestration_log.log_deployments_event(
                "deployment_completed", task_id=task_id, plan_id=str(pid), status="completed"
            )
        execution_log.log_execution_event(
            "execution_completed", task_id=task_id, plan_id=str(pid), status="completed"
        )
        return {"terminal": "completed", "plan_id": str(pid)}

    ready = execution_dependencies.ready_steps(plan, now_ts=now_ts)
    if not ready:
        task_registry.update_task_state(st, task_id, "waiting")
        execution_plan.update_plan_timestamp(plan)
        execution_log.log_execution_event(
            "execution_waiting", task_id=task_id, plan_id=str(pid), status="waiting"
        )
        return {"terminal": "waiting", "plan_id": str(pid)}

    step = ready[0]
    sid = str(step.get("step_id"))
    step["status"] = "running"
    execution_log.log_execution_event(
        "execution_step_started",
        task_id=task_id,
        plan_id=str(pid),
        step_id=sid,
        status="running",
        source_queue=source_queue or "",
    )

    if step.get("fail_once"):
        step.pop("fail_once", None)
        execution_retry.schedule_step_retry(plan, step, "simulated_failure", now_ts=now_ts)
        task_registry.update_task_state(st, task_id, "retrying")
        execution_memory.set_continuation(st, task_id, last_step=sid, phase="retry")
        execution_plan.update_plan_timestamp(plan)
        return {"terminal": "retrying", "plan_id": str(pid), "step_id": sid}

    # Successful step body (OpenClaw parity placeholder — real tools wire in later).
    outs = list(step.get("outputs") or [])
    outs.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ok": True})
    step["outputs"] = outs
    step["status"] = "completed"
    execution_checkpoint.save_checkpoint(
        st, str(pid), sid, task_id=task_id, outputs=outs, metadata={"source_queue": source_queue or ""}
    )
    execution_memory.append_output(st, task_id, "step_complete", sid)
    execution_memory.set_continuation(st, task_id, last_completed_step=sid)
    execution_plan.update_plan_timestamp(plan)
    _reconcile_blocked_labels(plan)

    if execution_plan.all_steps_terminal(plan):
        plan["status"] = "completed"
        task_registry.update_task_state(st, task_id, "completed")
        t_done = task_registry.get_task(st, task_id) or {}
        if str(t_done.get("type") or "") == "deploy":
            deps = st.setdefault("deployments", [])
            if isinstance(deps, list):
                deps.append(
                    {
                        "task_id": task_id,
                        "plan_id": str(pid),
                        "status": "completed",
                        "stage": plan.get("deployment_stage"),
                        "recovered": bool((plan.get("deployment_recovery") or {}).get("resumed")),
                    }
                )
            orchestration_log.log_deployments_event(
                "deployment_completed", task_id=task_id, plan_id=str(pid), status="completed"
            )
        execution_log.log_execution_event(
            "execution_completed", task_id=task_id, plan_id=str(pid), status="completed"
        )
        return {"terminal": "completed", "plan_id": str(pid), "step_id": sid}

    task_registry.update_task_state(st, task_id, "running")
    execution_log.log_execution_event(
        "execution_step_completed",
        task_id=task_id,
        plan_id=str(pid),
        step_id=sid,
        status="running",
    )
    return {"terminal": "running", "plan_id": str(pid), "step_id": sid}
