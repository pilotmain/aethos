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
from app.execution import tool_step as tool_step_mod
from app.execution import workflow_events
from app.orchestration import orchestration_log
from app.orchestration import task_registry


_TOOL_TYPES = frozenset(
    {
        "shell",
        "noop",
        "file_read",
        "file_write",
        "file_patch",
        "workspace_list",
        "workspace_search",
        "deploy",
        "http_request",
        "internal_api",
    }
)


def _sync_deployment_terminal(st: dict[str, Any], task_id: str, plan: dict[str, Any], terminal: str) -> None:
    from app.deployments.deployment_runtime import sync_deployment_terminal

    sync_deployment_terminal(st, task_id=task_id, plan=plan, terminal=terminal)


def _step_runs_tools(step: dict[str, Any]) -> bool:
    tblk = step.get("tool")
    if isinstance(tblk, dict) and str(tblk.get("name") or "").strip():
        return True
    return str(step.get("type") or "").strip() in _TOOL_TYPES


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
        from app.planning.replanning_runtime import on_plan_terminal_failure

        on_plan_terminal_failure(st, task_id=task_id, plan_id=str(pid), reason="missing_plan")
        return {"terminal": "failed", "plan_id": str(pid), "reason": "missing_plan"}

    if not execution_dependencies.validate_plan_dependency_dag(plan):
        task_registry.update_task_state(st, task_id, "failed", reason="invalid_dependency_dag")
        _note_supervisor(st, error="dependency_cycle")
        from app.planning.replanning_runtime import on_plan_terminal_failure

        on_plan_terminal_failure(st, task_id=task_id, plan_id=str(pid), reason="dependency_cycle")
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
        _sync_deployment_terminal(st, task_id, plan, "failed")
        from app.planning.replanning_runtime import on_plan_terminal_failure

        on_plan_terminal_failure(st, task_id=task_id, plan_id=str(pid), reason="any_step_failed")
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
        _sync_deployment_terminal(st, task_id, plan, "completed")
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
    from app.deployments.deployment_runtime import note_deploy_step_started

    note_deploy_step_started(st, task_id=task_id, plan=plan, step=step)
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
        from app.planning.adaptive_execution import notify_retry_scheduled

        notify_retry_scheduled(
            st, task_id=task_id, plan_id=str(pid), step_id=sid, reason="simulated_failure"
        )
        return {"terminal": "retrying", "plan_id": str(pid), "step_id": sid}

    start_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    step["started_at"] = start_iso

    if _step_runs_tools(step):
        tname = tool_step_mod.step_tool_name(step)
        result = tool_step_mod.execute_tool_step(step)
        step["result"] = result
        ok = tool_step_mod.tool_result_ok(tname, result)
        complete_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        step["completed_at"] = complete_iso
        outs = [{"ts": complete_iso, "tool": tname, "result": result}]
        step["outputs"] = list(step.get("outputs") or []) + outs
        wf_status = "completed" if ok else "failed"
        workflow_events.log_tool_event(
            f"tool_step_{wf_status}",
            task_id=task_id,
            plan_id=str(pid),
            step_id=sid,
            tool=tname,
            status=wf_status,
        )
        if (
            tname in ("file_write", "file_patch")
            and ok
            and isinstance(result, dict)
            and result.get("path")
        ):
            execution_memory.append_file_mutation(
                st,
                task_id,
                path=str(result.get("path") or ""),
                action=tname,
                tool_name=tname,
                step_id=sid,
                before_hash=result.get("before_sha256"),
                after_hash=result.get("after_sha256"),
            )
        if not ok:
            reason = str(result.get("error") or result.get("stderr") or "tool_failed")[:2000]
            step["error"] = reason
            max_r = int(step.get("max_retries") or 3)
            if step.get("retryable", True) and int(step.get("retry_count") or 0) < max_r:
                execution_retry.schedule_step_retry(plan, step, reason, now_ts=now_ts)
                task_registry.update_task_state(st, task_id, "retrying")
                execution_memory.set_continuation(st, task_id, last_step=sid, phase="retry")
                execution_plan.update_plan_timestamp(plan)
                from app.planning.adaptive_execution import notify_retry_scheduled

                notify_retry_scheduled(st, task_id=task_id, plan_id=str(pid), step_id=sid, reason=reason)
                return {"terminal": "retrying", "plan_id": str(pid), "step_id": sid}
            step["status"] = "failed"
            execution_checkpoint.save_checkpoint(
                st,
                str(pid),
                sid,
                task_id=task_id,
                outputs=list(step.get("outputs") or []),
                metadata={"source_queue": source_queue or "", "tool_failed": True},
            )
            execution_plan.update_plan_timestamp(plan)
            _reconcile_blocked_labels(plan)
            task_registry.update_task_state(st, task_id, "failed")
            plan["status"] = "failed"
            execution_log.log_execution_event(
                "execution_failed", task_id=task_id, plan_id=str(pid), status="failed"
            )
            _sync_deployment_terminal(st, task_id, plan, "failed")
            from app.planning.replanning_runtime import on_plan_terminal_failure

            on_plan_terminal_failure(st, task_id=task_id, plan_id=str(pid), reason=reason)
            return {"terminal": "failed", "plan_id": str(pid), "step_id": sid}
        step["error"] = None
        step["status"] = "completed"
    else:
        outs = list(step.get("outputs") or [])
        outs.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ok": True})
        step["outputs"] = outs
        step["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        step["status"] = "completed"

    execution_checkpoint.save_checkpoint(
        st, str(pid), sid, task_id=task_id, outputs=list(step.get("outputs") or []), metadata={"source_queue": source_queue or ""}
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
        _sync_deployment_terminal(st, task_id, plan, "completed")
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
