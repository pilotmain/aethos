# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Rollback metadata + orchestration (checkpoint-oriented; no forced infra actions)."""

from __future__ import annotations

from typing import Any

from app.deployments.deployment_registry import get_deployment, upsert_deployment
from app.orchestration import orchestration_log
from app.runtime.events.runtime_events import emit_runtime_event
from app.runtime.runtime_state import utc_now_iso


def start_rollback(st: dict[str, Any], deployment_id: str, *, reason: str = "") -> dict[str, Any] | None:
    row = get_deployment(st, deployment_id)
    if not row or not row.get("rollback_available"):
        return None
    ts = utc_now_iso()
    rb = dict(row.get("rollback") or {})
    rb.update({"status": "running", "started_at": ts, "reason": (reason or "")[:2000]})
    upsert_deployment(
        st,
        deployment_id,
        {"rollback": rb, "status": "running", "updated_at": ts},
    )
    orchestration_log.append_json_log("rollback", "rollback_started", deployment_id=deployment_id, reason=reason[:500])
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
    rb.update({"status": "completed" if success else "failed", "completed_at": ts})
    upsert_deployment(st, deployment_id, {"rollback": rb, "updated_at": ts, "rollback_available": False})
    orchestration_log.append_json_log(
        "rollback",
        "rollback_completed" if success else "rollback_failed",
        deployment_id=deployment_id,
    )
    emit_runtime_event(
        st,
        "deployment_rollback_completed",
        deployment_id=deployment_id,
        user_id=str(row.get("user_id") or ""),
        environment_id=str(row.get("environment_id") or ""),
        status="completed" if success else "failed",
    )
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["rollback_completed_total"] = int(m.get("rollback_completed_total") or 0) + 1
    return get_deployment(st, deployment_id)
