# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control runtime intelligence APIs (Phase 2 Step 8)."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.plugins.plugin_loader import load_all_plugins
from app.plugins.plugin_registry import list_plugin_manifests
from app.services.events.bus import list_events, subscribe, unsubscribe
from app.services.mission_control.runtime_intelligence import (
    build_agents_slice,
    build_deployments_slice,
    build_mission_control_runtime,
    build_providers_slice,
    build_runtime_events_slice,
    build_runtime_health,
    build_runtime_metrics_slice,
    build_tasks_slice,
)
from app.services.mission_control.runtime_panels import build_runtime_panels
from app.services.mission_control.runtime_event_intelligence import events_for_ws_replay
from app.services.mission_control.orchestration_runtime_snapshot import build_orchestration_runtime_snapshot

router = APIRouter(prefix="/mission-control", tags=["mission-control-runtime"])


@router.get("/runtime")
def mc_runtime(db: Session = Depends(get_db), app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return build_mission_control_runtime(db, user_id=app_user_id)


def _lightweight_slice(slice_name: str, app_user_id: str) -> dict:
    from app.services.mission_control.runtime_hydration import get_lightweight_slice

    return get_lightweight_slice(slice_name, app_user_id)


@router.get("/office")
def mc_office(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return _lightweight_slice("workers", app_user_id).get("office") or {}


@router.get("/agents")
def mc_agents(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return build_agents_slice(app_user_id)


@router.get("/tasks")
def mc_tasks(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return build_tasks_slice(app_user_id)


@router.get("/deployments")
def mc_deployments(_: str = Depends(get_valid_web_user_id)) -> dict:
    return build_deployments_slice()


@router.get("/providers")
def mc_providers(_: str = Depends(get_valid_web_user_id)) -> dict:
    return build_providers_slice()


@router.get("/runtime-health")
def mc_runtime_health(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return build_runtime_health(app_user_id, None)


@router.get("/runtime-events")
def mc_runtime_events(
    limit: int = Query(80, ge=1, le=500),
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    return build_runtime_events_slice(limit=limit)


@router.get("/runtime-metrics")
def mc_runtime_metrics(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return build_runtime_metrics_slice(app_user_id)


@router.get("/plugins")
def mc_plugins(_: str = Depends(get_valid_web_user_id)) -> dict:
    return {"plugins": list_plugin_manifests(), "loaded": load_all_plugins()}


@router.get("/runtime-panels")
def mc_runtime_panels(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return build_runtime_panels(app_user_id)


@router.get("/runtime-trace")
def mc_runtime_trace(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_truth_cache import get_cached_runtime_truth
    from app.services.mission_control.runtime_truth import build_runtime_truth

    truth = get_cached_runtime_truth(app_user_id, lambda uid: build_runtime_truth(user_id=uid))
    return {
        "ownership_trace": truth.get("ownership_trace") or [],
        "operator_traces": truth.get("operator_traces") or {},
        "routing_summary": truth.get("routing_summary"),
    }


@router.get("/runtime-traces")
def mc_runtime_traces(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_ownership import build_all_operator_traces

    return build_all_operator_traces(app_user_id)


def _truth_slice(app_user_id: str) -> dict:
    from app.services.mission_control.runtime_truth import build_runtime_truth
    from app.services.mission_control.runtime_truth_cache import get_cached_runtime_truth

    return get_cached_runtime_truth(app_user_id, lambda uid: build_runtime_truth(user_id=uid))


@router.get("/runtime/health")
def mc_runtime_enterprise_health(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return _lightweight_slice("health", app_user_id)


@router.get("/runtime/timeline")
def mc_runtime_timeline(
    limit: int = Query(40, ge=1, le=80),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.services.mission_control.runtime_hydration import build_incremental_timeline

    return build_incremental_timeline(limit=limit)


@router.get("/runtime/workers")
def mc_runtime_workers_slice(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return _lightweight_slice("workers", app_user_id)


@router.get("/runtime/deployments")
def mc_runtime_deployments_slice(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return _lightweight_slice("deployments", app_user_id)


@router.get("/runtime/providers")
def mc_runtime_providers_slice(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return _lightweight_slice("providers", app_user_id)


@router.get("/runtime/governance")
def mc_runtime_governance_slice(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return _lightweight_slice("governance", app_user_id)


@router.get("/runtime/recommendations")
def mc_runtime_recommendations_slice(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return _lightweight_slice("recommendations", app_user_id)


@router.get("/runtime/intelligence")
def mc_runtime_intelligence_slice(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return _lightweight_slice("intelligence", app_user_id)


@router.get("/runtime/continuity")
def mc_runtime_continuity_slice(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return _lightweight_slice("continuity", app_user_id)


@router.get("/runtime/performance")
def mc_runtime_performance(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return {
        "runtime_performance": t.get("runtime_performance") or {},
        "hydration_metrics": t.get("hydration_metrics") or {},
        "operational_responsiveness": t.get("operational_responsiveness") or {},
        "runtime_scalability": t.get("runtime_scalability") or {},
        "runtime_scalability_health": t.get("runtime_scalability_health") or {},
        "payload_discipline": t.get("payload_discipline") or {},
        "operational_pressure": t.get("operational_pressure") or {},
        "runtime_query_efficiency": t.get("runtime_query_efficiency") or {},
    }


@router.get("/runtime/scalability")
def mc_runtime_scalability(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return {
        "runtime_scalability_health": t.get("runtime_scalability_health") or {},
        "governance_scalability": t.get("governance_scalability") or {},
        "enterprise_operational_views": t.get("enterprise_operational_views") or {},
        "payload_discipline": t.get("payload_discipline") or {},
    }


@router.get("/runtime/workers/summaries")
def mc_runtime_worker_summaries(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=48),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.services.mission_control.worker_scalability import list_worker_summaries

    return list_worker_summaries(app_user_id, page=page, page_size=page_size)


@router.get("/governance/search")
def mc_governance_search(
    q: str | None = Query(None),
    limit: int = Query(24, ge=1, le=64),
    offset: int = Query(0, ge=0),
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.services.mission_control.governance_search import search_governance_entries

    return search_governance_entries(q, limit=limit, offset=offset)


@router.get("/governance/filter")
def mc_governance_filter(
    severity: str | None = Query(None),
    actor: str | None = Query(None),
    kind: str | None = Query(None),
    provider: str | None = Query(None),
    worker_id: str | None = Query(None),
    deployment_id: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(24, ge=1, le=64),
    offset: int = Query(0, ge=0),
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.services.mission_control.governance_search import filter_governance_entries

    return filter_governance_entries(
        severity=severity,
        actor=actor,
        kind=kind,
        provider=provider,
        worker_id=worker_id,
        deployment_id=deployment_id,
        category=category,
        limit=limit,
        offset=offset,
    )


@router.get("/timeline/search")
def mc_timeline_search(
    q: str | None = Query(None),
    kind: str | None = Query(None),
    actor: str | None = Query(None),
    limit: int = Query(24, ge=1, le=48),
    offset: int = Query(0, ge=0),
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.services.mission_control.runtime_timeline_hydration import search_timeline_entries

    return search_timeline_entries(q, limit=limit, offset=offset, kind=kind, actor=actor)


@router.get("/runtime/overview")
def mc_runtime_overview(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return t.get("runtime_overview") or t.get("enterprise_operator_experience", {}).get("runtime_overview") or {}


@router.get("/runtime/narratives")
def mc_runtime_narratives(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return {
        "operational_narratives": t.get("operational_narratives") or {},
        "runtime_stories": t.get("runtime_stories") or {},
    }


@router.get("/runtime/calmness")
def mc_runtime_calmness(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return {
        "runtime_calmness": t.get("runtime_calmness") or {},
        "operational_quality": t.get("operational_quality") or {},
    }


@router.get("/runtime/operator-experience")
def mc_enterprise_operator_experience(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return t.get("enterprise_operator_experience") or {}


@router.get("/governance/overview")
def mc_governance_overview(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.governance_experience import build_governance_overview

    return build_governance_overview(_truth_slice(app_user_id))


@router.get("/workers/overview")
def mc_workers_overview(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return t.get("worker_runtime_cohesion") or t.get("unified_worker_state") or {}


@router.get("/providers/overview")
def mc_providers_overview(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.provider_governance_visibility import (
        build_provider_governance,
        build_provider_trust,
    )

    t = _truth_slice(app_user_id)
    return {
        "providers": t.get("providers"),
        "governance": build_provider_governance(t),
        "trust": build_provider_trust(t),
        "runtime_identity_label": "Provider",
    }


@router.get("/execution/visibility")
def mc_execution_visibility(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return t.get("execution_visibility") or {}


@router.get("/runtime/accountability")
def mc_runtime_accountability(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return {
        "runtime_accountability": t.get("runtime_accountability") or {},
        "operational_trust_score": t.get("operational_trust_score"),
        "governance_integrity": t.get("governance_integrity") or {},
    }


@router.get("/runtime/escalations")
def mc_runtime_escalations(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return {
        "runtime_escalations": t.get("runtime_escalations") or {},
        "escalation_visibility": t.get("escalation_visibility") or {},
        "escalation_history": t.get("escalation_history") or [],
    }


@router.get("/governance/trust")
def mc_governance_trust(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return {
        "operational_trust_score": t.get("operational_trust_score"),
        "governance_integrity": t.get("governance_integrity") or {},
        "enterprise_trust_panels": t.get("enterprise_trust_panels") or {},
    }


@router.get("/providers/governance")
def mc_providers_governance(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.provider_governance_visibility import build_provider_governance

    return build_provider_governance()


@router.get("/providers/trust")
def mc_providers_trust(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.provider_governance_visibility import build_provider_trust

    return build_provider_trust()


@router.get("/providers/history")
def mc_providers_history(
    limit: int = Query(24, ge=1, le=64),
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.services.mission_control.provider_governance_visibility import build_provider_history

    return build_provider_history(limit=limit)


@router.get("/workers/accountability")
def mc_workers_accountability(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.worker_accountability import (
        build_worker_accountability,
        build_worker_governance,
        build_worker_operational_quality,
    )

    t = _truth_slice(app_user_id)
    return {
        "worker_accountability": t.get("worker_accountability") or build_worker_accountability(t, user_id=app_user_id),
        "worker_governance": t.get("worker_governance") or build_worker_governance(t),
        "worker_operational_quality": t.get("worker_operational_quality") or build_worker_operational_quality(t),
    }


@router.get("/automation/trust")
def mc_automation_trust(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.automation_governance import build_automation_governance, build_automation_trust

    return {"automation_trust": build_automation_trust(), "automation_governance": build_automation_governance()}


@router.get("/timeline/window")
def mc_timeline_window(
    limit: int = Query(24, ge=1, le=48),
    offset: int = Query(0, ge=0),
    group_by: str | None = Query(None),
    severity: str | None = Query(None),
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.services.mission_control.runtime_timeline_hydration import build_timeline_window

    return build_timeline_window(limit=limit, offset=offset, group_by=group_by, severity=severity)


@router.get("/operational-summary")
def mc_operational_summary(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return t.get("operational_summary") or {}


@router.get("/runtime/cohesion")
def mc_runtime_cohesion(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    t = _truth_slice(app_user_id)
    return t.get("runtime_cohesion") or {}


@router.get("/governance/summary")
def mc_governance_summary(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.runtime_governance import build_governance_timeline

    t = _truth_slice(app_user_id)
    return {
        "timeline": build_governance_timeline(limit=24),
        "unified": t.get("unified_operational_timeline"),
        "coordination": t.get("operational_coordination"),
    }


@router.get("/differentiators")
def mc_differentiators(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return _truth_slice(app_user_id).get("differentiators") or {}


@router.get("/privacy-posture")
def mc_privacy_posture(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.privacy_operational_posture import build_privacy_operational_posture

    return build_privacy_operational_posture()


@router.get("/brain-routing")
def mc_brain_routing(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.brain_routing_visibility import build_brain_routing_panel

    return build_brain_routing_panel()


@router.get("/operational-intelligence")
def mc_operational_intelligence(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.orchestration_runtime_snapshot import build_orchestration_runtime_snapshot
    from app.services.operational_intelligence_engine import build_operational_intelligence_engine

    return build_operational_intelligence_engine(build_orchestration_runtime_snapshot(app_user_id))


@router.get("/runtime-insights")
def mc_runtime_insights(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.orchestration_runtime_snapshot import build_orchestration_runtime_snapshot
    from app.services.operational_intelligence_engine import build_operational_intelligence_engine

    eng = build_operational_intelligence_engine(build_orchestration_runtime_snapshot(app_user_id))
    return {
        "runtime_insights": eng.get("runtime_insights"),
        "enterprise_operational_state": eng.get("enterprise_operational_state"),
        "summaries": eng.get("summaries"),
    }


@router.get("/runtime-recommendations")
def mc_runtime_recommendations(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.orchestration_runtime_snapshot import build_orchestration_runtime_snapshot
    from app.services.runtime_recommendations import build_runtime_recommendations

    return build_runtime_recommendations(build_orchestration_runtime_snapshot(app_user_id))


@router.get("/enterprise-runtime")
def mc_enterprise_runtime(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.enterprise_runtime_visibility import build_enterprise_runtime_panels

    return build_enterprise_runtime_panels(_truth_slice(app_user_id))


@router.post("/automation-packs/{pack_id}/run")
def mc_run_automation_pack(
    pack_id: str,
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.runtime.automation_pack_runtime import run_automation_pack

    return run_automation_pack(pack_id)


@router.get("/governance/risks")
def mc_governance_risks(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.workspace_runtime_intelligence import build_operational_risk
    from app.services.operational_intelligence_engine import build_intelligence_signals

    return {
        "operational_risk": build_operational_risk(),
        "signals": build_intelligence_signals(None),
    }


@router.get("/governance")
def mc_governance(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.runtime_governance import build_governance_timeline

    return build_governance_timeline()


@router.get("/workspace-intelligence")
def mc_workspace_intelligence(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.workspace_runtime_intelligence import build_workspace_intelligence

    return build_workspace_intelligence()


@router.get("/workspace-risks")
def mc_workspace_risks(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.workspace_runtime_intelligence import build_operational_risk

    return build_operational_risk()


@router.get("/research-chains")
def mc_research_chains(
    project_id: str | None = Query(None),
    limit: int = Query(12, ge=1, le=32),
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.runtime.workspace_operational_memory import list_research_chains

    return {"chains": list_research_chains(project_id=project_id, limit=limit)}


@router.get("/research-chains/{chain_id}")
def mc_research_chain_detail(
    chain_id: str,
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.services.research_continuity import build_research_chain_view

    return build_research_chain_view(chain_id)


@router.get("/operator-continuity")
def mc_operator_continuity(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.operator_continuity import build_operator_continuity_truth

    return build_operator_continuity_truth()


@router.get("/worker-collaboration")
def mc_worker_collaboration(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.worker_collaboration_visibility import build_worker_collaboration_chains

    return {"chains": build_worker_collaboration_chains()}


@router.get("/deliverables/{deliverable_id}/relationships")
def mc_deliverable_relationships(
    deliverable_id: str,
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.runtime.workspace_operational_memory import relationships_for_deliverable

    return {"deliverable_id": deliverable_id, "relationships": relationships_for_deliverable(deliverable_id)}


@router.get("/runtime-workers")
def mc_runtime_workers(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.mission_control.runtime_worker_visibility import build_runtime_workers_view

    return build_runtime_workers_view(app_user_id)


@router.get("/runtime-confidence")
def mc_runtime_confidence(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return _truth_slice(app_user_id).get("runtime_confidence") or {}


@router.get("/worker-deliverables")
def mc_worker_deliverables(
    q: str | None = Query(None),
    worker_id: str | None = Query(None),
    handle: str | None = Query(None),
    deliverable_type: str | None = Query(None, alias="type"),
    task_id: str | None = Query(None),
    project_id: str | None = Query(None),
    provider: str | None = Query(None),
    status: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    limit: int = Query(16, ge=1, le=48),
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.runtime.worker_operational_memory import search_deliverables

    return {
        "deliverables": search_deliverables(
            query=q,
            worker_id=worker_id,
            deliverable_type=deliverable_type,
            handle=handle,
            task_id=task_id,
            project_id=project_id,
            provider=provider,
            status=status,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
    }


@router.get("/deliverables")
def mc_deliverables_list(
    q: str | None = Query(None),
    worker_id: str | None = Query(None),
    handle: str | None = Query(None),
    deliverable_type: str | None = Query(None, alias="type"),
    task_id: str | None = Query(None),
    project_id: str | None = Query(None),
    provider: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(24, ge=1, le=48),
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.runtime.worker_operational_memory import search_deliverables

    return {
        "deliverables": search_deliverables(
            query=q,
            worker_id=worker_id,
            deliverable_type=deliverable_type,
            handle=handle,
            task_id=task_id,
            project_id=project_id,
            provider=provider,
            status=status,
            limit=limit,
        )
    }


@router.get("/deliverables/{deliverable_id}")
def mc_deliverable_detail(
    deliverable_id: str,
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.services.mission_control.worker_deliverable_ops import build_deliverable_detail

    return build_deliverable_detail(deliverable_id)


@router.get("/deliverables/{deliverable_id}/export")
def mc_deliverable_export(
    deliverable_id: str,
    format: str = Query("markdown", alias="format"),
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.services.mission_control.worker_deliverable_ops import export_deliverable

    return export_deliverable(deliverable_id, fmt=format)


@router.get("/runtime-workers/{worker_id}")
def mc_runtime_worker_detail(
    worker_id: str,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.services.mission_control.worker_deliverable_ops import build_worker_detail

    return build_worker_detail(worker_id, user_id=app_user_id)


@router.get("/runtime-workers/{worker_id}/deliverables")
def mc_runtime_worker_deliverables(
    worker_id: str,
    limit: int = Query(16, ge=1, le=48),
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.runtime.worker_operational_memory import list_deliverables_for_worker

    return {"worker_id": worker_id, "deliverables": list_deliverables_for_worker(worker_id, limit=limit)}


@router.get("/runtime-workers/{worker_id}/memory")
def mc_runtime_worker_memory(
    worker_id: str,
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.runtime.worker_operational_memory import build_worker_memory

    return {"worker_id": worker_id, "memory": build_worker_memory(worker_id)}


@router.get("/runtime-workers/{worker_id}/continuations")
def mc_runtime_worker_continuations(
    worker_id: str,
    limit: int = Query(12, ge=1, le=32),
    _: str = Depends(get_valid_web_user_id),
) -> dict:
    from app.runtime.worker_operational_memory import list_continuations_for_worker

    return {"worker_id": worker_id, "continuations": list_continuations_for_worker(worker_id, limit=limit)}


@router.get("/automation-packs")
def mc_automation_packs(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.plugins.automation_packs import list_automation_packs_with_health

    return {"packs": list_automation_packs_with_health()}


@router.websocket("/runtime/ws")
async def mc_runtime_ws(ws: WebSocket) -> None:
    """Live Mission Control runtime events (bounded bus replay + subscribe)."""
    await ws.accept()
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=500)
    loop = asyncio.get_running_loop()

    def push(event: dict) -> None:
        t = str(event.get("type") or "")
        if not (t.startswith("mission_control.") or t.startswith("runtime.")):
            return

        def _enqueue() -> None:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        try:
            loop.call_soon_threadsafe(_enqueue)
        except RuntimeError:
            pass

    for row in events_for_ws_replay(limit=40):
        push(
            {
                "type": f"mission_control.{row.get('event_type')}",
                "timestamp": row.get("timestamp"),
                "payload": row,
            }
        )
    for ev in list_events()[-20:]:
        if isinstance(ev, dict):
            push(ev)
    subscribe(push)

    async def pump() -> None:
        while True:
            ev = await queue.get()
            await ws.send_json(ev)

    pump_task = asyncio.create_task(pump())
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        pump_task.cancel()
        try:
            await pump_task
        except asyncio.CancelledError:
            pass
        unsubscribe(push)
