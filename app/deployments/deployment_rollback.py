# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Rollback metadata + orchestration (checkpoint-oriented; no forced infra actions)."""

from __future__ import annotations

import uuid
from typing import Any

from app.deployments.deployment_lifecycle import transition_deployment_stage
from app.deployments.deployment_registry import get_deployment, upsert_deployment
from app.environments import environment_locks
from app.orchestration import orchestration_log
from app.runtime.events.runtime_events import emit_runtime_event
from app.runtime.runtime_state import utc_now_iso


def start_rollback(st: dict[str, Any], deployment_id: str, *, reason: str = "") -> dict[str, Any] | None:
    row = get_deployment(st, deployment_id)
    if not row or not row.get("rollback_available"):
        return None
    ts = utc_now_iso()
    rid = f"rb_{uuid.uuid4().hex[:12]}"
    rb = dict(row.get("rollback") or {})
    rb.update(
        {
            "rollback_id": rid,
            "status": "running",
            "stage": "rolling_back",
            "created_at": rb.get("created_at") or ts,
            "updated_at": ts,
            "started_at": ts,
            "retry_count": int(rb.get("retry_count") or 0),
            "reason": (reason or "")[:2000],
            "artifacts": list(rb.get("artifacts") or []) if isinstance(rb.get("artifacts"), list) else [],
            "logs": list(rb.get("logs") or []) if isinstance(rb.get("logs"), list) else [],
        }
    )
    logs = rb["logs"]
    if isinstance(logs, list):
        logs.append({"ts": ts, "message": "rollback_start", "detail": (reason or "")[:1500]})
        rb["logs"] = logs[-500:]
    upsert_deployment(
        st,
        deployment_id,
        {"rollback": rb, "updated_at": ts},
    )
    transition_deployment_stage(st, deployment_id, "rolling_back", reason=reason or "rollback", sync_status=True)
    orchestration_log.append_json_log("rollback", "rollback_started", deployment_id=deployment_id, reason=reason[:500])
    emit_runtime_event(
        st,
        "deployment_rollback_created",
        deployment_id=deployment_id,
        rollback_id=rid,
        user_id=str(row.get("user_id") or ""),
        environment_id=str(row.get("environment_id") or ""),
    )
    emit_runtime_event(
        st,
        "deployment_rollback_started",
        deployment_id=deployment_id,
        user_id=str(row.get("user_id") or ""),
        environment_id=str(row.get("environment_id") or ""),
        status="running",
    )
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["rollback_started_total"] = int(m.get("rollback_started_total") or 0) + 1
    return get_deployment(st, deployment_id)


def complete_rollback(st: dict[str, Any], deployment_id: str, *, success: bool) -> dict[str, Any] | None:
    row = get_deployment(st, deployment_id)
    if not row:
        return None
    ts = utc_now_iso()
    rb = dict(row.get("rollback") or {})
    rb.update({"status": "completed" if success else "failed", "completed_at": ts, "updated_at": ts, "stage": "rolled_back" if success else "failed"})
    logs = list(rb.get("logs") or [])
    logs.append({"ts": ts, "message": "rollback_complete" if success else "rollback_failed"})
    rb["logs"] = logs[-500:]
    upsert_deployment(
        st,
        deployment_id,
        {"rollback": rb, "updated_at": ts, "rollback_available": False},
    )
    env_id = str(row.get("environment_id") or "")
    if success:
        transition_deployment_stage(st, deployment_id, "rolled_back", reason="rollback_complete", sync_status=True)
        environment_locks.release_lock(st, env_id, deployment_id)
    else:
        transition_deployment_stage(st, deployment_id, "failed", reason="rollback_failed", sync_status=True)
    orchestration_log.append_json_log(
        "rollback",
        "rollback_completed" if success else "rollback_failed",
        deployment_id=deployment_id,
    )
    emit_runtime_event(
        st,
        "deployment_rollback_completed" if success else "deployment_rollback_failed",
        deployment_id=deployment_id,
        user_id=str(row.get("user_id") or ""),
        environment_id=env_id,
        status="completed" if success else "failed",
    )
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["rollback_completed_total"] = int(m.get("rollback_completed_total") or 0) + 1
    return get_deployment(st, deployment_id)
