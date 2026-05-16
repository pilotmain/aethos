# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Consolidated runtime health model (Phase 2 Step 10)."""

from __future__ import annotations

from typing import Any


def build_consolidated_runtime_health(
    ort: dict[str, Any],
    *,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rel = ort.get("reliability") or {}
    cont = ort.get("continuity") or {}
    queue_p = int(rel.get("queue_pressure_events") or 0) > 0 or int(ort.get("queued_tasks") or 0) > 8
    retry_p = int(rel.get("retry_pressure_events") or 0) > 0 or int(ort.get("retrying_tasks") or 0) > 0
    deploy_p = int(rel.get("deployment_pressure_events") or 0) > 0
    provider_failures = int(rel.get("provider_failures") or 0)
    recovery_active = int(cont.get("restart_recovery_attempts") or 0) > int(cont.get("restart_recovery_successes") or 0)
    evs = events or []
    critical_events = sum(1 for e in evs if str(e.get("severity") or "") == "critical")
    warning_events = sum(1 for e in evs if str(e.get("severity") or "") == "warning")

    severity = "info"
    status = "healthy"
    if recovery_active and not critical_events:
        severity = "warning"
        status = "recovering"
    elif not rel.get("integrity_ok", True) or critical_events > 0:
        severity = "critical"
        status = "critical"
    elif provider_failures > 0 or retry_p:
        severity = "error"
        status = "degraded"
    elif queue_p or deploy_p or warning_events > 3:
        severity = "warning"
        status = "warning"

    color = {
        "healthy": "green",
        "warning": "amber",
        "degraded": "amber",
        "critical": "red",
        "recovering": "violet",
    }.get(status, "green")

    return {
        "status": status,
        "severity": severity,
        "color": color,
        "queue_pressure": bool(queue_p),
        "retry_pressure": bool(retry_p),
        "deployment_pressure": bool(deploy_p),
        "recovery_active": bool(recovery_active),
        "provider_failures": provider_failures,
        "critical_events": critical_events,
        "integrity_ok": bool(rel.get("integrity_ok", True)),
        "queued_tasks": ort.get("queued_tasks"),
        "active_tasks": ort.get("active_tasks"),
        "retrying_tasks": ort.get("retrying_tasks"),
    }


def _category_state(status: str) -> str:
    if status in ("healthy", "warning", "degraded", "recovering", "critical"):
        return status
    return "healthy"


def build_enterprise_operational_health(truth: dict[str, Any]) -> dict[str, Any]:
    """Cohesive enterprise health across ten categories (Phase 3 Step 11)."""
    rh = truth.get("runtime_health") or {}
    conf = truth.get("runtime_confidence") or {}
    panels = truth.get("enterprise_runtime_panels") or {}
    recs = truth.get("runtime_recommendations") or {}
    privacy = truth.get("privacy_posture") or truth.get("privacy") or {}

    runtime_status = _category_state(str(rh.get("status") or "healthy"))
    provider_status = _category_state(
        str((panels.get("provider_stability") or {}).get("status") or "healthy")
        if isinstance(panels.get("provider_stability"), dict)
        else ("warning" if rh.get("provider_failures") else "healthy")
    )
    if rh.get("provider_failures"):
        provider_status = "degraded"

    deployment_status = _category_state(
        str((panels.get("deployment_reliability") or {}).get("status") or "healthy")
        if isinstance(panels.get("deployment_reliability"), dict)
        else ("warning" if rh.get("deployment_pressure") else "healthy")
    )
    automation_status = _category_state(
        "warning"
        if (panels.get("automation_health") or {}).get("failed_packs")
        else "healthy"
    )
    governance_status = _category_state(
        str((panels.get("governance_health") or {}).get("enterprise_state", {}).get("health") or "healthy")
        if isinstance(panels.get("governance_health"), dict)
        else "healthy"
    )
    worker_status = _category_state(
        "warning"
        if (truth.get("operational_intelligence") or {}).get("worker_reliability", {}).get("low_reliability_workers")
        else "healthy"
    )
    workspace_status = _category_state(
        str((panels.get("workspace_health") or {}).get("confidence", {}).get("level") or "stable")
        if isinstance((panels.get("workspace_health") or {}).get("confidence"), dict)
        else "healthy"
    )
    if workspace_status == "stable":
        workspace_status = "healthy"
    elif workspace_status == "degraded":
        workspace_status = "warning"

    continuity_status = _category_state("recovering" if rh.get("recovery_active") else "healthy")
    rec_conf = recs.get("recommendations") or []
    avg_conf = (
        sum(float(r.get("confidence") or 0) for r in rec_conf if isinstance(r, dict)) / len(rec_conf)
        if rec_conf
        else 1.0
    )
    recommendation_status = "warning" if avg_conf < 0.6 else "healthy"
    privacy_status = _category_state(str(privacy.get("mode") or "observe") if privacy.get("mode") != "block" else "warning")

    categories = {
        "runtime": runtime_status,
        "provider": provider_status,
        "deployment": deployment_status,
        "automation": automation_status,
        "governance": governance_status,
        "worker": worker_status,
        "workspace": workspace_status,
        "continuity": continuity_status,
        "recommendation_confidence": recommendation_status,
        "privacy": privacy_status,
    }
    order = ["critical", "degraded", "warning", "recovering", "healthy"]
    overall = "healthy"
    for level in order:
        if any(v == level for v in categories.values()):
            overall = level
            break

    return {
        "overall": overall,
        "categories": categories,
        "runtime_confidence": (conf.get("runtime_confidence") or {}) if isinstance(conf, dict) else {},
    }
