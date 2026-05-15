"""Orchestration boot + high-level coordination."""

from __future__ import annotations

import logging
from typing import Any

from app.orchestration import orchestration_log
from app.orchestration import task_recovery
from app.orchestration import task_scheduler

from app.execution import execution_continuation

_LOG = logging.getLogger(__name__)


def orchestration_boot(st: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Run startup recovery on in-memory state (caller persists).
    Starts background scheduler unless skipped (pytest / env).
    """
    if st is None:
        from app.runtime.runtime_state import load_runtime_state

        st = load_runtime_state()
    try:
        from app.runtime.events.runtime_events import emit_runtime_event

        emit_runtime_event(st, "runtime_recovery_started", stage="orchestration_boot")
    except Exception:
        pass
    rec = task_recovery.recover_orchestration_on_boot(st)
    ex = execution_continuation.recover_execution_on_boot(st)
    from app.runtime.sessions.session_recovery import recover_runtime_sessions_on_boot
    from app.runtime.events.runtime_metrics import bump_runtime_boot

    sess = recover_runtime_sessions_on_boot(st)
    bump_runtime_boot(st)
    from app.runtime.integrity.runtime_audit import log_runtime_audit
    from app.runtime.integrity.runtime_cleanup import cleanup_runtime_state

    clean = cleanup_runtime_state(st)
    from app.deployments.deployment_recovery import recover_deployments_on_boot
    from app.environments.environment_recovery import recover_environments_on_boot

    dep_rec = recover_deployments_on_boot(st)
    env_rec = recover_environments_on_boot(st)
    from app.agents.agent_recovery import recover_agent_coordination_on_boot

    cord = recover_agent_coordination_on_boot(st)
    from app.planning.planner_runtime import recover_planning_on_boot

    plan_rec = recover_planning_on_boot(st)
    log_runtime_audit(
        "orchestration_boot_cleanup",
        queues_pruned=int(clean.get("queues_pruned") or 0),
        plans_pruned=int(clean.get("plans_pruned") or 0),
        events_trimmed=int(clean.get("events_trimmed") or 0),
        memory_buckets_pruned=int(clean.get("memory_buckets_pruned") or 0),
        checkpoints_pruned=int(clean.get("checkpoints_pruned") or 0),
        deployments_recovering=int(dep_rec.get("deployments_marked_recovering") or 0),
        environments_recovering=int(env_rec.get("environments_touched") or 0),
        coordination_agents_recovering=int(cord.get("agents_marked_recovering") or 0),
        coordination_loops_waiting=int(cord.get("loops_marked_waiting") or 0),
        planning_records_restored=int(plan_rec.get("planning_records_restored") or 0),
    )
    orchestration_log.log_orchestration_event(
        "orchestration_boot",
        recovery_tasks=rec.get("count", 0),
        execution_resume_steps=ex.get("count", 0),
        runtime_sessions_recovered=sess.get("count", 0),
        cleanup_queues_pruned=clean.get("queues_pruned"),
        cleanup_plans_pruned=clean.get("plans_pruned"),
    )
    try:
        from app.runtime.events.runtime_events import emit_runtime_event

        emit_runtime_event(
            st,
            "runtime_recovery_completed",
            recovery_tasks=int(rec.get("count") or 0),
            execution_resume_steps=int(ex.get("count") or 0),
            cleanup_queues_pruned=int(clean.get("queues_pruned") or 0),
        )
    except Exception:
        pass
    task_scheduler.start_scheduler_background()
    _LOG.info(
        "orchestration.boot recovery=%s execution=%s sessions=%s",
        rec.get("count", 0),
        ex.get("count", 0),
        sess.get("count", 0),
    )
    return {"orchestration": rec, "execution": ex, "sessions": sess}
