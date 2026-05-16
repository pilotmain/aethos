# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control runtime event helpers (Phase 2 Step 8–9)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_event_intelligence import (
    infer_category_severity,
    list_normalized_events,
    normalize_runtime_event,
    persist_runtime_event,
)

_MC_EVENT_TYPES = frozenset(
    {
        "task_created",
        "task_started",
        "task_completed",
        "task_failed",
        "deployment_started",
        "deployment_completed",
        "deployment_failed",
        "deployment_rollback_started",
        "agent_spawned",
        "agent_suspended",
        "agent_expired",
        "agent_recovered",
        "brain_selected",
        "provider_selected",
        "repair_started",
        "repair_verified",
        "repair_redeploy_started",
        "runtime_recovered",
        "queue_pressure",
        "retry_pressure",
        "privacy_redaction",
        "privacy_block",
        "plugin_loaded",
        "plugin_failed",
        "worker_deliverable_persisted",
        "worker_deliverable_failed",
        "worker_continuation_queued",
        "automation_pack_executed",
        "automation_pack_failed",
        "automation_pack_disabled",
        "governance_warning",
        "provider_fallback_triggered",
        "operational_risk_escalated",
        "workspace_degradation_detected",
        "plugin_instability_detected",
    }
)


def emit_mc_runtime_event(
    event_type: str,
    *,
    correlation_id: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    et = (event_type or "").strip()
    if et not in _MC_EVENT_TYPES:
        et = et or "runtime_event"
    cat, sev = infer_category_severity(et)
    row = normalize_runtime_event(
        et,
        payload=fields,
        correlation_id=correlation_id,
        category=category or cat,
        severity=severity or sev,
    )
    persist_runtime_event(row)
    try:
        from app.services.events.bus import publish

        publish(
            {
                "type": f"mission_control.{et}",
                "timestamp": row.get("timestamp"),
                "mission_id": fields.get("mission_id"),
                "agent": fields.get("agent_id"),
                "payload": row,
            }
        )
    except Exception:
        pass
    return row


def recent_mc_runtime_events(*, limit: int = 80, category: str | None = None) -> list[dict[str, Any]]:
    return list_normalized_events(limit=limit, category=category)
