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
    from app.services.operational_intelligence import build_operational_intelligence

    return build_operational_intelligence(build_orchestration_runtime_snapshot(app_user_id))


@router.get("/governance")
def mc_governance(_: str = Depends(get_valid_web_user_id)) -> dict:
    from app.services.runtime_governance import build_governance_audit

    return build_governance_audit()


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
