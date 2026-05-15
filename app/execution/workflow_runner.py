"""Persist workflow tasks + plans and enqueue for the orchestration dispatcher."""

from __future__ import annotations

from typing import Any

from app.execution import execution_plan
from app.execution import workflow_builder
from app.execution import workflow_events
from app.orchestration import task_queue
from app.orchestration import task_registry


def persist_operator_workflow(
    st: dict[str, Any],
    text: str,
    *,
    user_id: str,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """
    Build steps from operator ``text``, register a task, create plan, attach, enqueue.
    Mutates ``st``; caller should :func:`~app.runtime.runtime_state.save_runtime_state`.
    """
    steps = workflow_builder.build_steps_from_operator_text(text)
    tid = task_registry.put_task(
        st,
        {
            "type": "workflow",
            "agent_id": agent_id or "workflow",
            "user_id": user_id,
            "state": "queued",
            "source": "gateway_workflow",
            "operator_text": (text or "")[:4000],
        },
    )
    pid = execution_plan.create_plan(st, tid, steps)
    execution_plan.attach_plan_to_task(st, tid, pid)
    task_queue.enqueue_task_id(st, "execution_queue", tid)
    workflow_events.log_workflow_event(
        "workflow_enqueued",
        task_id=tid,
        plan_id=pid,
        user_id=user_id,
        step_count=len(steps),
    )
    return {"task_id": tid, "plan_id": pid, "state": "queued", "steps": len(steps)}
