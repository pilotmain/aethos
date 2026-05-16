# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control live operational panels (Phase 2 Step 9)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_agents import agent_runtime_metrics, list_runtime_agents
from app.services.mission_control.runtime_ownership import build_ownership_chains
from app.services.mission_control.runtime_event_intelligence import list_normalized_events
from app.services.operator_context import build_operator_context_panel
from app.services.mission_control.orchestration_runtime_snapshot import build_orchestration_runtime_snapshot


def build_runtime_panels(user_id: str | None) -> dict[str, Any]:
    from app.services.mission_control.runtime_intelligence import build_brain_visibility, build_runtime_health

    ort = build_orchestration_runtime_snapshot(user_id)
    op = build_operator_context_panel()
    brain = build_brain_visibility()
    rel = ort.get("reliability") or {}
    cont = ort.get("continuity") or {}
    agents = list_runtime_agents(include_expired=False)
    return {
        "runtime_health": {
            **build_runtime_health(user_id, ort),
            "reliability": rel,
            "continuity": cont,
            "queue_pressure": rel.get("queue_pressure_events"),
            "retry_pressure": rel.get("retry_pressure_events"),
            "deployment_pressure": rel.get("deployment_pressure_events"),
            "provider_failures": rel.get("provider_failures"),
        },
        "brain_routing": brain,
        "provider_operations": {
            "inventory": op.get("provider_inventory"),
            "recent_actions": (op.get("recent_provider_actions") or [])[-16:],
            "latest_repairs": op.get("latest_repair_contexts"),
            "deployment_identities": op.get("deployment_identities"),
            "suggested_fixes": op.get("suggested_fixes"),
        },
        "runtime_agents": {
            "agents": agents,
            "metrics": agent_runtime_metrics(),
            "ownership": build_ownership_chains(user_id),
        },
        "privacy_runtime": {
            "mode": brain.get("brain", {}).get("privacy_mode"),
            "recent_events": [
                e
                for e in list_normalized_events(limit=30)
                if str(e.get("category") or "") == "privacy"
            ],
        },
        "recovery": {
            "continuity": cont,
            "recovered_agents": agent_runtime_metrics().get("recovered_agents"),
            "runtime_events": [
                e for e in list_normalized_events(limit=20) if "recover" in str(e.get("event_type") or "")
            ],
        },
    }
