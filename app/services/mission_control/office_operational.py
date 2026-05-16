# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Office operational view — calm, runtime-backed (Phase 3 Step 3)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_agents import ORCHESTRATOR_ID, office_agent_states
from app.services.mission_control.runtime_event_intelligence import aggregate_events_for_display


def build_office_operational_view(truth: dict[str, Any], *, user_id: str | None = None) -> dict[str, Any]:
    """Enriched Office payload derived from runtime truth (no duplicate orchestration reads)."""
    health = truth.get("runtime_health") or {}
    routing = truth.get("routing_summary") or {}
    privacy = truth.get("privacy_posture") or {}
    plugins = truth.get("plugins") or {}
    agents = office_agent_states()
    orch_row = next((a for a in agents if a.get("agent_id") == ORCHESTRATOR_ID), None)
    critical = [e for e in (truth.get("runtime_events") or []) if str(e.get("severity")) == "critical"]
    return {
        "orchestrator": {
            "agent_id": ORCHESTRATOR_ID,
            "role": "orchestrator",
            "persistent": True,
            "status": (orch_row or {}).get("office_state", "active"),
            "health": health.get("status"),
        },
        "agents": agents,
        "active_worker_count": sum(
            1 for a in agents if not a.get("system") and a.get("office_state") not in ("offline", None)
        ),
        "recent_events": aggregate_events_for_display(limit=10, suppress_info_when_noisy=True),
        "critical_events": critical[:6],
        "routing": routing,
        "privacy_mode": (privacy.get("privacy_posture") or {}).get("mode") or routing.get("privacy_mode"),
        "pressure": {
            "queue": health.get("queue_pressure"),
            "retry": health.get("retry_pressure"),
            "deployment": health.get("deployment_pressure"),
        },
        "plugin_health": {
            "healthy": plugins.get("healthy_count"),
            "failed": plugins.get("failed_count"),
        },
        "active_tasks": health.get("active_tasks"),
        "queued_tasks": health.get("queued_tasks"),
        "repair_tracked": (truth.get("operational_intelligence") or {}).get("repair_tracked"),
        "runtime_confidence": (truth.get("runtime_confidence") or {}).get("runtime_confidence"),
        "confidence_summary": ((truth.get("runtime_confidence") or {}).get("operational_stability") or {}).get(
            "summary"
        ),
    }
