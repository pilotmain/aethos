# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Structured deployment failure diagnostics (OpenClaw operational parity)."""

from __future__ import annotations

from typing import Any

from app.deployments.deployment_registry import get_deployment, upsert_deployment
from app.environments import environment_registry
from app.orchestration import orchestration_log
from app.runtime.events.runtime_events import emit_runtime_event
from app.runtime.runtime_state import utc_now_iso


def record_deployment_failure_diagnostics(
    st: dict[str, Any],
    deployment_id: str,
    *,
    task_id: str,
    plan_id: str,
    failed_stage: str,
    failure_reason: str,
    plan: dict[str, Any] | None = None,
) -> None:
    """Persist diagnostics on the deployment row and emit a runtime event."""
    did = str(deployment_id)
    ts = utc_now_iso()
    row = get_deployment(st, did) or {}
    env_id = str(row.get("environment_id") or "")
    env = environment_registry.get_environment(st, env_id) if env_id else None
    env_health = str((env or {}).get("status") or "unknown")
    snap: dict[str, Any] = {
        "ts": ts,
        "task_id": str(task_id),
        "plan_id": str(plan_id),
        "metrics": dict(st.get("runtime_metrics") or {}) if isinstance(st.get("runtime_metrics"), dict) else {},
        "queues": {
            qn: len(st.get(qn) or []) if isinstance(st.get(qn), list) else 0
            for qn in (
                "execution_queue",
                "deployment_queue",
                "agent_queue",
                "channel_queue",
                "recovery_queue",
                "scheduler_queue",
            )
        },
    }
    if isinstance(plan, dict):
        snap["plan_status"] = str(plan.get("status") or "")
        steps = plan.get("steps")
        snap["plan_steps"] = len(steps) if isinstance(steps, list) else 0
    arts = row.get("artifacts")
    diag = {
        "failure_reason": (failure_reason or "")[:4000],
        "failed_stage": (failed_stage or "")[:128],
        "retry_recommendation": "Inspect deploy logs and fix the failing step; re-run the workflow when the root cause is resolved.",
        "rollback_recommendation": "If rollback_available is true, POST /deployments/{id}/rollback to restore the prior known-good state.",
        "environment_health_impact": f"environment {env_id or 'n/a'} status={env_health}",
        "artifact_refs": list(arts)[:80] if isinstance(arts, list) else [],
        "runtime_snapshot_at_failure": snap,
    }
    upsert_deployment(
        st,
        did,
        {
            "failure_reason": diag["failure_reason"][:2000],
            "failed_stage": diag["failed_stage"],
            "deployment_diagnostics": diag,
            "updated_at": ts,
        },
    )
    orchestration_log.append_json_log(
        "deployment_health",
        "deployment_diagnostics_recorded",
        deployment_id=did,
        plan_id=str(plan_id),
        task_id=str(task_id),
    )
    emit_runtime_event(
        st,
        "deployment_diagnostics_recorded",
        deployment_id=did,
        task_id=str(task_id),
        plan_id=str(plan_id),
        failed_stage=diag["failed_stage"],
    )
