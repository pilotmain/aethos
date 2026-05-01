"""Mission Control dashboard API (V1) — summary + developer cleanup actions.

Phase 15 — locked contracts (stable JSON/WebSocket; do not rename or remove):

- ``GET /mission-control/state`` — execution snapshot (:func:`build_execution_snapshot`).
- ``GET /mission-control/graph`` — derived graph from the same snapshot.
- ``GET /mission-control/events/timeline`` — deque-backed event history.
- ``WebSocket /mission-control/events/ws`` — live JSON stream (same bus).
- ``POST /mission-control/gateway/run`` — Nexa gateway admission.

Orchestration summary (distinct from execution state) remains at
``GET /mission-control/summary``.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.models.nexa_next_runtime import NexaMission
from app.services.audit_service import audit
from app.services.mission_control.cleanup_actions import (
    cancel_assignment,
    clear_spawn_group,
    clear_workspace_reports,
    delete_or_hide_agent_job,
    delete_or_hide_assignment,
    dismiss_agent_job,
    mission_control_delete_custom_agent,
    reset_mission_control,
)
from app.services.mission_control.db_purge import (
    mission_control_data_inventory,
    purge_mission_control_database_for_user,
)
from app.services.mission_control.graph_builder import build_graph_cached
from app.services.mission_control.nexa_next_state import build_execution_snapshot
from app.services.mission_control.read_model import build_mission_control_summary
from app.services.mission_control.ui_state import dismiss_attention_item

router = APIRouter(prefix="/mission-control", tags=["mission-control"])


class MissionControlResetBody(BaseModel):
    include_custom_agents: bool = False
    hard_delete: bool = False


class MissionControlPurgeBody(BaseModel):
    """Nuclear cleanup: same as reset but always disables custom agents."""
    hard_delete: bool = False


class MissionControlSqlPurgeBody(BaseModel):
    """Hard-delete MC-related DB rows for the authenticated user (dev flag required)."""

    include_audit_logs: bool = False
    include_pending_permissions: bool = True
    include_custom_agents: bool = True
    clear_workspace_files: bool = True


@router.get("/data-inventory")
def mc_data_inventory(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    """Counts of DB rows + report files that feed Mission Control for this user (read-only)."""
    return mission_control_data_inventory(db, app_user_id)


def _mc_sql_purge_or_403(
    body: MissionControlSqlPurgeBody,
    db: Session,
    app_user_id: str,
) -> dict:
    if not get_settings().nexa_mission_control_sql_purge:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SQL purge disabled. Set NEXA_MISSION_CONTROL_SQL_PURGE=true (development only).",
        )
    return purge_mission_control_database_for_user(
        db,
        app_user_id,
        include_audit_logs=body.include_audit_logs,
        include_pending_permissions=body.include_pending_permissions,
        include_custom_agents=body.include_custom_agents,
        clear_workspace_files=body.clear_workspace_files,
    )


@router.post("/database/purge-sql")
def mc_purge_sql(
    body: MissionControlSqlPurgeBody,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    """Hard-delete orchestration, jobs, org roles/orgs, optional permissions/agents/audit for this user."""
    return _mc_sql_purge_or_403(body, db, app_user_id)


@router.post("/reset-hard")
def mc_reset_hard(
    body: MissionControlSqlPurgeBody,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    """Same behavior as POST /database/purge-sql (runbook alias: hard SQL erase for this user)."""
    return _mc_sql_purge_or_403(body, db, app_user_id)


@router.get("/summary")
def mission_control_summary(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
    hours: int = Query(24, ge=1, le=168, description="Look-back window for trust activity and aggregations"),
) -> dict:
    return build_mission_control_summary(db, app_user_id, hours=hours)


@router.get("/state")
def mission_control_state(
    db: Session = Depends(get_db),
    user_id: str | None = Query(None, description="Filter missions/tasks/artifacts to this user"),
) -> dict:
    """Nexa-Next execution state — DB-backed missions, tasks, artifacts, plus event bus and privacy streams."""
    return build_execution_snapshot(db, user_id=user_id)


@router.get("/graph")
def mission_control_graph(
    db: Session = Depends(get_db),
    user_id: str | None = Query(None, description="Same scope as /state"),
) -> dict:
    """Agent/task nodes and dependency edges for Mission Control visualization."""
    state = build_execution_snapshot(db, user_id=user_id)
    return build_graph_cached(state)


@router.get("/events/timeline")
def mission_control_events_timeline() -> list:
    """Ordered timeline of runtime events (deque-backed bus)."""
    from app.services.events.bus import list_events

    return list_events()


@router.websocket("/events/ws")
async def mission_control_events_ws(ws: WebSocket) -> None:
    """Push JSON events as they are published (live Mission Control stream)."""
    from app.services.events.bus import subscribe, unsubscribe

    await ws.accept()
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=500)

    def push(event: dict) -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass

    subscribe(push)

    async def pump() -> None:
        while True:
            ev = await queue.get()
            await ws.send_json(ev)

    pump_task = asyncio.create_task(pump())
    try:
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


@router.post("/gateway/run")
def mission_control_gateway_run(
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    """Run user text through :class:`~app.services.gateway.runtime.NexaGateway`."""
    text = str(payload.get("text") or "")
    user_id = str(payload.get("user_id") or "dev_user")

    from app.services.gateway.runtime import NexaGateway

    return NexaGateway().handle_message(text, user_id, db=db)


@router.post("/replay/{mission_id}")
def mission_control_replay_mission(
    mission_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    """Re-run stored mission input text through the gateway (same privacy guarantees)."""
    from app.services.gateway.runtime import NexaGateway

    m = db.get(NexaMission, mission_id)
    if m is None or m.user_id != app_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    raw = (m.input_text or "").strip()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mission has no stored input_text (created before replay support)",
        )
    return NexaGateway().handle_message(raw, app_user_id, db=db)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.post("/assignments/{assignment_id}/cancel")
def mc_cancel_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    out = cancel_assignment(db, user_id=app_user_id, assignment_id=assignment_id)
    if not out.get("ok"):
        raise _not_found()
    return out


def _mc_delete_assignment(
    db: Session,
    *,
    app_user_id: str,
    assignment_id: int,
    hard_delete: bool,
) -> dict:
    out = delete_or_hide_assignment(
        db, user_id=app_user_id, assignment_id=assignment_id, hard_delete=hard_delete
    )
    if not out.get("ok"):
        raise _not_found()
    return out


@router.delete("/assignments/{assignment_id}")
def mc_delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
    hard_delete: bool = Query(False, description="Hard delete (requires NEXA_DEV_ALLOW_HARD_DELETE=true)"),
) -> dict:
    return _mc_delete_assignment(db, app_user_id=app_user_id, assignment_id=assignment_id, hard_delete=hard_delete)


@router.post("/assignments/{assignment_id}/delete")
def mc_delete_assignment_post(
    assignment_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
    hard_delete: bool = Query(False, description="Hard delete (requires NEXA_DEV_ALLOW_HARD_DELETE=true)"),
) -> dict:
    """POST alias for browsers/proxies that block DELETE (same behavior as DELETE)."""
    return _mc_delete_assignment(db, app_user_id=app_user_id, assignment_id=assignment_id, hard_delete=hard_delete)


@router.post("/spawn-groups/{spawn_group_id}/clear")
def mc_clear_spawn_group(
    spawn_group_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    out = clear_spawn_group(db, user_id=app_user_id, spawn_group_id=spawn_group_id)
    if not out.get("ok"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=out.get("error", "clear_failed"))
    return out


@router.post("/reports/clear")
def mc_clear_reports(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    return clear_workspace_reports(db, user_id=app_user_id)


@router.post("/jobs/{job_id}/dismiss")
def mc_dismiss_job(
    job_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    out = dismiss_agent_job(db, user_id=app_user_id, job_id=job_id)
    if not out.get("ok"):
        raise _not_found()
    return out


def _mc_delete_job(
    db: Session,
    *,
    app_user_id: str,
    job_id: int,
    hard_delete: bool,
) -> dict:
    out = delete_or_hide_agent_job(db, user_id=app_user_id, job_id=job_id, hard_delete=hard_delete)
    if not out.get("ok"):
        raise _not_found()
    return out


@router.delete("/jobs/{job_id}")
def mc_delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
    hard_delete: bool = Query(False, description="Hard delete (requires NEXA_DEV_ALLOW_HARD_DELETE=true)"),
) -> dict:
    return _mc_delete_job(db, app_user_id=app_user_id, job_id=job_id, hard_delete=hard_delete)


@router.post("/jobs/{job_id}/delete")
def mc_delete_job_post(
    job_id: int,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
    hard_delete: bool = Query(False, description="Hard delete (requires NEXA_DEV_ALLOW_HARD_DELETE=true)"),
) -> dict:
    """POST alias for browsers/proxies that block DELETE."""
    return _mc_delete_job(db, app_user_id=app_user_id, job_id=job_id, hard_delete=hard_delete)


def _mc_delete_custom_agent(db: Session, *, app_user_id: str, handle: str) -> dict:
    out = mission_control_delete_custom_agent(db, user_id=app_user_id, handle=handle)
    if not out.get("ok"):
        raise _not_found()
    return out


@router.delete("/custom-agents/{handle}")
def mc_delete_custom_agent_route(
    handle: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    return _mc_delete_custom_agent(db, app_user_id=app_user_id, handle=handle)


@router.post("/custom-agents/{handle}/delete")
def mc_delete_custom_agent_post(
    handle: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    """POST alias for browsers/proxies that block DELETE."""
    return _mc_delete_custom_agent(db, app_user_id=app_user_id, handle=handle)


@router.post("/reset")
def mc_reset(
    body: MissionControlResetBody,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    return reset_mission_control(
        db,
        user_id=app_user_id,
        include_custom_agents=body.include_custom_agents,
        hard_delete=body.hard_delete,
    )


@router.post("/purge")
def mc_purge_everything(
    body: MissionControlPurgeBody,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    """Clear MC state for this user and disable all custom agents (soft-delete semantics unless hard_delete + dev flag)."""
    out = reset_mission_control(
        db,
        user_id=app_user_id,
        include_custom_agents=True,
        hard_delete=body.hard_delete,
    )
    return {**out, "purged": True}


@router.post("/attention/{item_id}/dismiss")
def mc_dismiss_attention(
    item_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    iid = (item_id or "").strip()
    if not iid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty item id")
    dismiss_attention_item(app_user_id, iid)
    audit(
        db,
        event_type="mission_control.attention.dismissed",
        actor="nexa",
        user_id=app_user_id,
        message=f"Dismissed attention item {iid}",
        metadata={"attention_id": iid},
    )
    return {"ok": True, "attention_id": iid, "dismissed": True}
