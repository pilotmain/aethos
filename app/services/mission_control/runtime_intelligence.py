# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control runtime intelligence payloads (Phase 2 Step 8)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.brain.brain_events import recent_brain_decisions
from app.core.config import get_settings
from app.privacy.privacy_policy import current_privacy_mode
from app.runtime.runtime_agents import (
    agent_runtime_metrics,
    list_runtime_agents,
    office_agent_states,
    office_topology,
    recover_runtime_agents_after_restart,
    sweep_expired_agents,
)
from app.runtime.runtime_state import load_runtime_state
from app.services.mission_control.mc_runtime_events import recent_mc_runtime_events
from app.services.mission_control.runtime_metrics_cache import get_cached_metrics
from app.services.mission_control.orchestration_runtime_snapshot import build_orchestration_runtime_snapshot
from app.services.operator_context import build_operator_context_panel
from app.services.plugins.registry import plugin_manifest


def build_brain_visibility() -> dict[str, Any]:
    s = get_settings()
    mode = current_privacy_mode(s)
    recent = recent_brain_decisions(limit=1)
    latest = recent[0] if recent else {}
    return {
        "brain": {
            "provider": latest.get("selected_provider"),
            "model": latest.get("selected_model"),
            "local_first": bool(
                getattr(s, "aethos_local_first_enabled", False) or getattr(s, "nexa_local_first", False)
            ),
            "fallback_used": bool(latest.get("fallback_used")),
            "privacy_mode": mode.value,
            "task": latest.get("task"),
            "reason": latest.get("reason"),
        },
        "recent_decisions": recent_brain_decisions(limit=8),
    }


def _runtime_metrics(st: dict[str, Any], ort: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(st.get("runtime_metrics") or {}) if isinstance(st.get("runtime_metrics"), dict) else {}
    rel = ort.get("reliability") or {}
    cont = ort.get("continuity") or {}
    repairs = (st.get("repair_contexts") or {}).get("latest_by_project") or {}
    repair_count = len(repairs) if isinstance(repairs, dict) else 0
    return {
        "token_usage_estimate": metrics.get("token_usage_estimate") or metrics.get("tokens_total"),
        "request_counts": metrics.get("request_counts") or {},
        "provider_distribution": metrics.get("provider_distribution") or {},
        "task_throughput": {
            "active": ort.get("active_tasks"),
            "queued": ort.get("queued_tasks"),
            "retrying": ort.get("retrying_tasks"),
        },
        "deployment_throughput": ort.get("deployment_summary") or {},
        "runtime_reliability": rel,
        "runtime_continuity": cont,
        "repair_tracked_projects": repair_count,
        "queue_pressure": rel.get("queue_pressure_events"),
        "retry_pressure": rel.get("retry_pressure_events"),
        "estimated_cost_usd": metrics.get("estimated_cost_usd"),
    }


def build_runtime_health(user_id: str | None, ort: dict[str, Any]) -> dict[str, Any]:
    hb = ort.get("heartbeat") or {}
    res = ort.get("resilience") or {}
    color = "green"
    if not res.get("integrity_ok", True):
        color = "red"
    elif int(ort.get("retrying_tasks") or 0) > 0:
        color = "amber"
    elif int(ort.get("queued_tasks") or 0) > 8:
        color = "amber"
    return {
        "status": hb.get("status") or "ok",
        "color": color,
        "integrity_ok": res.get("integrity_ok", True),
        "queued_tasks": ort.get("queued_tasks"),
        "active_tasks": ort.get("active_tasks"),
        "retrying_tasks": ort.get("retrying_tasks"),
        "user_id": user_id,
    }


def _build_runtime_panels(user_id: str) -> dict[str, Any]:
    from app.services.mission_control.runtime_panels import build_runtime_panels

    return build_runtime_panels(user_id)


def _build_metrics(user_id: str) -> dict[str, Any]:
    st = load_runtime_state()
    ort = build_orchestration_runtime_snapshot(user_id)
    return {**_runtime_metrics(st, ort), "agent_metrics": agent_runtime_metrics()}


def build_mission_control_runtime(db: Session, *, user_id: str) -> dict[str, Any]:
    """Unified runtime payload for Mission Control operational surface."""
    recover_runtime_agents_after_restart()
    sweep_expired_agents()
    st = load_runtime_state()
    ort = build_orchestration_runtime_snapshot(user_id)
    operator = build_operator_context_panel()
    brain = build_brain_visibility()
    agents = list_runtime_agents()
    metrics = get_cached_metrics(user_id, lambda uid: _build_metrics(uid))
    return {
        "runtime_health": build_runtime_health(user_id, ort),
        "orchestrator": agents.get("aethos_orchestrator"),
        "runtime_agents": agents,
        "office": office_topology(user_id),
        "panels": _build_runtime_panels(user_id),
        "tasks": ort.get("tasks") or [],
        "queues": ort.get("queue_depths") or {},
        "deployments": {
            "identities": operator.get("deployment_identities") or {},
            "summary": ort.get("deployment_summary") or {},
        },
        "providers": {
            "inventory": operator.get("provider_inventory"),
            "recent_actions": operator.get("recent_provider_actions"),
            "recent_nl_actions": operator.get("recent_nl_provider_actions"),
        },
        "operator_context": operator,
        "repair": operator.get("latest_repair_contexts") or {},
        "brain_visibility": brain,
        "privacy": {
            "mode": brain["brain"]["privacy_mode"],
            "events_tail": (ort.get("runtime_events_tail") or [])[-20:],
        },
        "runtime_events": recent_mc_runtime_events(limit=60),
        "runtime_metrics": metrics,
        "plugins": plugin_manifest(),
        "workflows": ort.get("workflows") or {},
    }


def build_agents_slice(user_id: str | None = None) -> dict[str, Any]:
    sweep_expired_agents()
    return {"runtime_agents": list_runtime_agents(), "office": {"agents": office_agent_states()}, "user_id": user_id}


def build_tasks_slice(user_id: str | None = None) -> dict[str, Any]:
    ort = build_orchestration_runtime_snapshot(user_id)
    return {"tasks": ort.get("tasks") or [], "queues": ort.get("queue_depths") or {}, "workflows": ort.get("workflows")}


def build_deployments_slice() -> dict[str, Any]:
    op = build_operator_context_panel()
    return {
        "deployment_identities": op.get("deployment_identities") or {},
        "project_registry": op.get("project_registry") or {},
        "latest_repairs": op.get("latest_repair_contexts") or {},
    }


def build_providers_slice() -> dict[str, Any]:
    op = build_operator_context_panel()
    return {
        "provider_inventory": op.get("provider_inventory"),
        "provider_ids": op.get("provider_ids"),
        "recent_provider_actions": op.get("recent_provider_actions"),
        "suggested_fixes": op.get("suggested_fixes"),
    }


def build_runtime_events_slice(*, limit: int = 80) -> dict[str, Any]:
    return {"events": recent_mc_runtime_events(limit=limit)}


def build_runtime_metrics_slice(user_id: str | None = None) -> dict[str, Any]:
    st = load_runtime_state()
    ort = build_orchestration_runtime_snapshot(user_id)
    return {"metrics": _runtime_metrics(st, ort)}
