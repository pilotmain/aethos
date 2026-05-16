# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control runtime intelligence — delegates to runtime_truth (Phase 2 Step 10)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.mission_control.runtime_truth import (
    build_brain_visibility,
    build_provider_routing_summary,
    build_runtime_panels_from_truth,
    build_runtime_truth,
)
from app.services.mission_control.runtime_event_intelligence import aggregate_events_for_display
from app.services.mission_control.runtime_metrics_cache import get_cached_metrics


def build_runtime_health(user_id: str | None, ort: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = build_runtime_truth(user_id=user_id)
    return truth.get("runtime_health") or {}


def build_mission_control_runtime(db: Session, *, user_id: str) -> dict[str, Any]:
    truth = build_runtime_truth(user_id=user_id)
    return {
        **truth,
        "panels": build_runtime_panels_from_truth(truth),
    }


def build_agents_slice(user_id: str | None = None) -> dict[str, Any]:
    truth = build_runtime_truth(user_id=user_id)
    return {
        "runtime_agents": truth.get("runtime_agents"),
        "runtime_agents_history": truth.get("runtime_agents_history"),
        "office": truth.get("office"),
        "user_id": user_id,
    }


def build_tasks_slice(user_id: str | None = None) -> dict[str, Any]:
    truth = build_runtime_truth(user_id=user_id)
    return {
        "tasks": truth.get("tasks") or [],
        "queues": truth.get("queues") or {},
        "workflows": truth.get("workflows") or {},
    }


def build_deployments_slice() -> dict[str, Any]:
    truth = build_runtime_truth(user_id=None)
    return {
        "deployment_identities": (truth.get("deployments") or {}).get("identities") or {},
        "project_registry": (truth.get("operator_context") or {}).get("project_registry") or {},
        "latest_repairs": truth.get("repair") or {},
    }


def build_providers_slice() -> dict[str, Any]:
    truth = build_runtime_truth(user_id=None)
    p = truth.get("providers") or {}
    return {
        "provider_inventory": p.get("inventory"),
        "provider_ids": (truth.get("operator_context") or {}).get("provider_ids"),
        "recent_provider_actions": p.get("recent_actions"),
        "suggested_fixes": (truth.get("operator_context") or {}).get("suggested_fixes"),
    }


def build_runtime_events_slice(*, limit: int = 80) -> dict[str, Any]:
    return {"events": aggregate_events_for_display(limit=limit)}


def build_runtime_metrics_slice(user_id: str | None = None) -> dict[str, Any]:
    truth = build_runtime_truth(user_id=user_id)
    return {"metrics": truth.get("runtime_metrics") or {}}
