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


@router.get("/office")
def mc_office(app_user_id: str = Depends(get_valid_web_user_id)) -> dict:
    return _truth_slice(app_user_id).get("office") or {}


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
