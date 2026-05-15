"""Route tasks from queues to execution (ordering + recovery coordination)."""

from __future__ import annotations

import logging
from typing import Any

from app.orchestration import orchestration_log
from app.orchestration import runtime_executor
from app.orchestration import task_queue
from app.orchestration import task_registry

_LOG = logging.getLogger(__name__)


def _pick_next_task_id(st: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (task_id, source_queue) — recovery_queue first, then execution_queue."""
    for qname in ("recovery_queue", "execution_queue"):
        tid = task_queue.dequeue_task_id(st, qname)
        if tid:
            return tid, qname
    return None, None


def dispatch_once(st: dict[str, Any]) -> dict[str, Any] | None:
    """
    Pop at most one task, transition state, execute, persist terminal state.
    Returns a small result dict or ``None`` if idle.
    """
    tid, src = _pick_next_task_id(st)
    if not tid:
        return None
    t = task_registry.get_task(st, tid)
    if not t:
        orchestration_log.log_orchestration_event(
            "dispatch_skipped_missing_task", task_id=tid, source_queue=src
        )
        return {"task_id": tid, "skipped": True, "reason": "missing_task"}

    prev = str(t.get("state") or "queued")

    # --- Autonomous execution (multi-step plans, deps, retries, checkpoints) ---
    if t.get("execution_plan_id"):
        from app.execution.execution_supervisor import tick_planned_task

        if prev in ("queued", "scheduled"):
            orchestration_log.log_orchestration_event(
                "task_started",
                task_id=tid,
                agent_id=t.get("agent_id"),
                status="running",
                source_queue=src,
            )
            if t.get("agent_id"):
                orchestration_log.log_agents_event(
                    "task_started", task_id=tid, agent_id=t.get("agent_id"), status="running"
                )
        plan_res = tick_planned_task(st, tid, source_queue=src or "")
        term = str(plan_res.get("terminal") or "failed") if plan_res else "failed"
        if term in ("running", "waiting", "retrying"):
            task_queue.enqueue_task_id(st, "execution_queue", tid)
        if term in ("completed", "failed", "cancelled"):
            final = task_registry.get_task(st, tid) or {}
            orchestration_log.log_orchestration_event(
                "task_finished",
                task_id=tid,
                status=str(final.get("state")),
                previous=prev,
            )
        _LOG.debug("orchestration.dispatch task=%s execution terminal=%s", tid, term)
        return {"task_id": tid, "terminal": term, "source_queue": src, "execution": plan_res}

    task_registry.update_task_state(st, tid, "running", dispatched_from=src or "")
    orchestration_log.log_orchestration_event(
        "task_started", task_id=tid, agent_id=t.get("agent_id"), status="running", source_queue=src
    )
    if t.get("agent_id"):
        orchestration_log.log_agents_event(
            "task_started", task_id=tid, agent_id=t.get("agent_id"), status="running"
        )

    terminal = runtime_executor.execute_task(st, tid)
    if terminal in task_registry.TASK_STATES:
        task_registry.update_task_state(st, tid, terminal)
    else:
        task_registry.update_task_state(st, tid, "failed", reason="bad_terminal_state")

    final = task_registry.get_task(st, tid) or {}
    orchestration_log.log_orchestration_event(
        "task_finished",
        task_id=tid,
        status=str(final.get("state")),
        previous=prev,
    )
    _LOG.debug("orchestration.dispatch task=%s terminal=%s", tid, terminal)
    return {"task_id": tid, "terminal": terminal, "source_queue": src}
