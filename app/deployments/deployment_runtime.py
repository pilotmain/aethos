# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Create/update deployment rows, emit runtime events, and bump metrics."""

from __future__ import annotations

from typing import Any

from app.deployments.deployment_artifacts import artifacts_from_plan
from app.deployments.deployment_environments import resolve_environment_id
from app.deployments.deployment_registry import get_deployment, upsert_deployment
from app.orchestration import orchestration_log
from app.runtime.events.runtime_events import emit_runtime_event
from app.runtime.runtime_state import utc_now_iso


def deployment_id_for_plan(plan_id: str) -> str:
    return f"dpl_{plan_id}"


def _metrics(st: dict[str, Any]) -> dict[str, Any]:
    m = st.setdefault("runtime_metrics", {})
    if not isinstance(m, dict):
        st["runtime_metrics"] = {}
        return st["runtime_metrics"]
    return m


def _bump(st: dict[str, Any], key: str, delta: int = 1) -> None:
    m = _metrics(st)
    m[key] = int(m.get(key) or 0) + delta


def plan_has_deploy_step(plan: dict[str, Any]) -> bool:
    for s in plan.get("steps") or []:
        if isinstance(s, dict) and str(s.get("type") or "") == "deploy":
            return True
    return False


def on_operator_plan_created_if_deploy(
    st: dict[str, Any],
    *,
    task_id: str,
    plan_id: str,
    user_id: str,
    session_id: str | None,
    steps: list[dict[str, Any]],
) -> str | None:
    """If the plan includes a deploy step, register ``deployment_created`` (idempotent)."""
    if not any(isinstance(s, dict) and str(s.get("type") or "") == "deploy" for s in steps):
        return None
    did = deployment_id_for_plan(plan_id)
    existing = get_deployment(st, did)
    if isinstance(existing, dict) and existing.get("created_logged"):
        return did
    ts = utc_now_iso()
    env_id = resolve_environment_id(st, explicit=None, user_id=user_id)
    upsert_deployment(
        st,
        did,
        {
            "deployment_id": did,
            "environment_id": env_id,
            "status": "running",
            "created_at": ts,
            "updated_at": ts,
            "workflow_id": str(plan_id),
            "task_id": str(task_id),
            "user_id": str(user_id),
            "session_id": str(session_id or ""),
            "artifacts": [],
            "logs": [],
            "retry_count": 0,
            "rollback_available": False,
            "rollback": {},
            "checkpoint": {"stage": "pending", "plan_id": str(plan_id)},
            "created_logged": True,
        },
    )
    orchestration_log.append_json_log(
        "deployment_health",
        "deployment_health_snapshot",
        deployment_id=did,
        environment_id=env_id,
        status="running",
    )
    emit_runtime_event(
        st,
        "deployment_created",
        deployment_id=did,
        task_id=str(task_id),
        plan_id=str(plan_id),
        user_id=str(user_id),
        environment_id=env_id,
        status="running",
    )
    from app.environments import environment_runtime

    environment_runtime.touch_deployment_count(st, env_id, delta=1)
    return did


def note_deploy_step_started(st: dict[str, Any], *, task_id: str, plan: dict[str, Any], step: dict[str, Any]) -> None:
    if str(step.get("type") or "") != "deploy":
        return
    pid = str(plan.get("plan_id") or plan.get("id") or "")
    if not pid:
        return
    did = deployment_id_for_plan(pid)
    row = upsert_deployment(st, did, {})
    if not row:
        return
    ts = utc_now_iso()
    first = not bool(row.get("execution_started_logged"))
    patch: dict[str, Any] = {
        "updated_at": ts,
        "status": "running",
        "checkpoint": {"stage": "deploy_step", "plan_id": pid, "step_id": str(step.get("step_id") or "")},
    }
    if first:
        patch["execution_started_logged"] = True
    upsert_deployment(st, did, patch)
    if first:
        emit_runtime_event(
            st,
            "deployment_started",
            deployment_id=did,
            task_id=str(task_id),
            plan_id=pid,
            user_id=str(row.get("user_id") or ""),
            environment_id=str(row.get("environment_id") or ""),
            status="running",
        )
        _bump(st, "deployment_started_total")


def sync_deployment_terminal(
    st: dict[str, Any],
    *,
    task_id: str,
    plan: dict[str, Any],
    terminal: str,
) -> None:
    """Update deployment record when a plan with deploy steps reaches a terminal task state."""
    if not plan_has_deploy_step(plan):
        return
    pid = str(plan.get("plan_id") or plan.get("id") or "")
    if not pid:
        return
    did = deployment_id_for_plan(pid)
    ts = utc_now_iso()
    arts = artifacts_from_plan(plan)
    prev = upsert_deployment(st, did, {})
    env_id = str(prev.get("environment_id") or resolve_environment_id(st, explicit=None, user_id=str(prev.get("user_id") or "")))
    status = "completed" if terminal == "completed" else "failed"
    logs = list(prev.get("logs") or [])
    if isinstance(logs, list):
        logs.append({"ts": ts, "message": f"terminal:{terminal}", "task_id": str(task_id)})
    upsert_deployment(
        st,
        did,
        {
            "updated_at": ts,
            "status": status,
            "artifacts": arts,
            "logs": logs[-500:],
            "checkpoint": {"stage": status, "plan_id": pid},
            "rollback_available": terminal == "completed",
        },
    )
    orchestration_log.log_deployments_event(
        "deployment_completed" if terminal == "completed" else "deployment_failed",
        deployment_id=did,
        task_id=str(task_id),
        plan_id=pid,
        status=status,
    )
    orchestration_log.append_json_log(
        "deployment_health",
        "deployment_health_snapshot",
        deployment_id=did,
        environment_id=env_id,
        status=status,
    )
    emit_runtime_event(
        st,
        "deployment_completed" if terminal == "completed" else "deployment_failed",
        deployment_id=did,
        task_id=str(task_id),
        plan_id=pid,
        user_id=str(prev.get("user_id") or ""),
        environment_id=env_id,
        status=status,
    )
    if terminal == "completed":
        _bump(st, "deployment_completed_total")
    else:
        _bump(st, "deployment_failed_total")
    from app.environments import environment_health

    environment_health.note_deployment_outcome(st, env_id, success=terminal == "completed")
