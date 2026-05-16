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
