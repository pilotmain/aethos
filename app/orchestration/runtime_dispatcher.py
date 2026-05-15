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
            try:
                from app.runtime.events.runtime_events import emit_runtime_event

                emit_runtime_event(
                    st,
                    "task_started",
                    task_id=tid,
                    user_id=str(t.get("user_id") or ""),
                    session_id=str(t.get("owner_session_id") or ""),
                    status="running",
                    agent_id=str(t.get("assigned_agent_id") or t.get("agent_id") or ""),
                )
            except Exception:
                pass
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
            try:
                from app.runtime.events.runtime_events import emit_runtime_event
                from app.runtime.events.runtime_metrics import bump_dispatch
                from app.runtime.sessions.session_registry import detach_task

                fs = str(final.get("state") or "")
                if fs == "completed":
                    emit_runtime_event(
                        st,
                        "task_completed",
                        task_id=tid,
                        user_id=str(final.get("user_id") or ""),
                        session_id=str(final.get("owner_session_id") or ""),
                        status=fs,
                    )
                elif fs == "failed":
                    emit_runtime_event(
                        st,
                        "task_failed",
                        task_id=tid,
                        user_id=str(final.get("user_id") or ""),
                        session_id=str(final.get("owner_session_id") or ""),
                        status=fs,
                    )
                if fs in ("completed", "failed"):
                    bump_dispatch(st, terminal=fs)
                osid = final.get("owner_session_id")
                if osid and fs in ("completed", "failed", "cancelled"):
                    detach_task(st, str(osid), tid)
                if fs == "completed" and str(final.get("type") or "") == "workflow":
                    emit_runtime_event(
                        st,
                        "workflow_completed",
                        task_id=tid,
                        plan_id=str(final.get("execution_plan_id") or ""),
                        user_id=str(final.get("user_id") or ""),
                        session_id=str(final.get("owner_session_id") or ""),
                        status="completed",
                    )
            except Exception:
                pass
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
    try:
        from app.runtime.events.runtime_events import emit_runtime_event

        emit_runtime_event(
            st,
            "task_started",
            task_id=tid,
            user_id=str(t.get("user_id") or ""),
            session_id=str(t.get("owner_session_id") or ""),
            status="running",
            agent_id=str(t.get("assigned_agent_id") or t.get("agent_id") or ""),
        )
    except Exception:
        pass

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
    try:
        from app.runtime.events.runtime_events import emit_runtime_event
        from app.runtime.events.runtime_metrics import bump_dispatch
        from app.runtime.sessions.session_registry import detach_task

        fs = str(final.get("state") or "")
        if fs == "completed":
            emit_runtime_event(
                st,
                "task_completed",
                task_id=tid,
                user_id=str(final.get("user_id") or ""),
                session_id=str(final.get("owner_session_id") or ""),
                status=fs,
            )
        elif fs == "failed":
            emit_runtime_event(
                st,
                "task_failed",
                task_id=tid,
                user_id=str(final.get("user_id") or ""),
                session_id=str(final.get("owner_session_id") or ""),
                status=fs,
            )
        if fs in ("completed", "failed"):
            bump_dispatch(st, terminal=fs)
        osid = final.get("owner_session_id")
        if osid and fs in ("completed", "failed", "cancelled"):
            detach_task(st, str(osid), tid)
    except Exception:
        pass
    _LOG.debug("orchestration.dispatch task=%s terminal=%s", tid, terminal)
    return {"task_id": tid, "terminal": terminal, "source_queue": src}
