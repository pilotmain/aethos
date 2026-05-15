"""Persist workflow tasks + plans and enqueue for the orchestration dispatcher."""

from __future__ import annotations

from typing import Any

from app.execution import execution_plan
from app.execution import workflow_builder
from app.execution import workflow_events
from app.orchestration import task_queue
from app.orchestration import task_registry
from app.runtime.events.runtime_events import emit_runtime_event
from app.runtime.sessions.session_manager import ensure_session_for_operator
from app.runtime.sessions.session_registry import attach_task


def persist_operator_workflow(
    st: dict[str, Any],
    text: str,
    *,
    user_id: str,
    agent_id: str | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    """
    Build steps from operator ``text``, register a task, create plan, attach, enqueue.
    Mutates ``st``; caller should :func:`~app.runtime.runtime_state.save_runtime_state`.
    """
    steps = workflow_builder.build_steps_from_operator_text(text)
    sid = ensure_session_for_operator(st, user_id, channel or "web")
    tid = task_registry.put_task(
        st,
        {
            "type": "workflow",
            "agent_id": agent_id or "workflow",
            "user_id": user_id,
            "state": "queued",
            "source": "gateway_workflow",
            "operator_text": (text or "")[:4000],
            "owner_session_id": sid,
            "owner_user_id": user_id,
            "assigned_agent_id": agent_id or "workflow",
        },
    )
    pid = execution_plan.create_plan(st, tid, steps)
    execution_plan.attach_plan_to_task(st, tid, pid)
    from app.deployments.deployment_runtime import on_operator_plan_created_if_deploy

    on_operator_plan_created_if_deploy(
        st, task_id=tid, plan_id=str(pid), user_id=user_id, session_id=sid, steps=steps
    )
    from app.planning.planner_runtime import ensure_planning_record_for_plan

    ensure_planning_record_for_plan(st, task_id=tid, plan_id=str(pid), user_id=user_id)
    task_queue.enqueue_task_id(st, "execution_queue", tid)
    attach_task(st, sid, tid)
    workflow_events.log_workflow_event(
        "workflow_enqueued",
        task_id=tid,
        plan_id=pid,
        user_id=user_id,
        step_count=len(steps),
    )
    emit_runtime_event(
        st,
        "task_created",
        task_id=tid,
        plan_id=pid,
        session_id=sid,
        user_id=user_id,
        status="queued",
    )
    emit_runtime_event(
        st,
        "workflow_created",
        task_id=tid,
        plan_id=pid,
        session_id=sid,
        user_id=user_id,
        status="queued",
    )
    return {"task_id": tid, "plan_id": pid, "session_id": sid, "state": "queued", "steps": len(steps)}
