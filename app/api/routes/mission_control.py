# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control dashboard API (V1) — summary + developer cleanup actions.

Phase 15 — locked contracts (stable JSON/WebSocket; do not rename or remove):

- ``GET /mission-control/state`` — execution snapshot (:func:`build_execution_snapshot`).
- ``GET /mission-control/graph`` — derived graph from the same snapshot.
- ``GET /mission-control/events/timeline`` — deque-backed event history.
- ``WebSocket /mission-control/events/ws`` — live JSON stream (same bus).
- ``POST /mission-control/gateway/run`` — Nexa gateway admission.
- ``POST /mission-control/override-alert`` — Phase 19 dismiss warning-level integrity alerts (authenticated).
- ``GET /mission-control/export/{mission_id}`` — Phase 20 export mission bundle (authenticated).
- ``POST /mission-control/import`` — Phase 20 import mission bundle (authenticated).
- ``POST /mission-control/autonomy/tasks/{task_id}/interrupt`` — Phase 44 interrupt autonomous task (authenticated).

Unified Mission Control payload (execution + dashboard) is ``GET /mission-control/state``.
``GET /mission-control/summary`` is gone (HTTP 410 — use ``/state``).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import get_valid_web_user_id
from app.models.autonomy import NexaAutonomousTask
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
from app.services.mission_control.export_import import export_mission_bundle, import_mission_bundle
from app.services.mission_control.graph_builder import build_graph_cached
from app.services.mission_control.nexa_next_state import (
    apply_integrity_alert_override,
    build_execution_snapshot,
)
from app.services.mission_control.ui_state import dismiss_attention_item
from app.services.autonomy.feedback import record_task_feedback

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


class IntegrityOverrideBody(BaseModel):
    """Acknowledge / dismiss warning-level integrity alerts (never secrets)."""

    alert_id: str
    action: Literal["ignore"]


class MissionControlGatewayRunBody(BaseModel):
    """
    POST /mission-control/gateway/run — tolerate ``text``, ``raw``, ``message``, or ``prompt``.

    Using an explicit model avoids FastAPI's strict ``dict`` body typing (clients that sent
    non-object JSON or relied only on ``raw`` saw *Input should be a valid dictionary*).
    """

    model_config = ConfigDict(extra="ignore")

    text: str | None = Field(default=None, description="Primary message field.")
    raw: str | None = Field(default=None, description="Alias used by some clients / docs.")
    message: str | None = Field(default=None, description="Alias (chat-shaped payloads).")
    prompt: str | None = Field(default=None, description="Alias for gateway-style prompts.")
    user_id: str | None = Field(default=None, description="Logical user id for GatewayContext.")

    workflow: bool = Field(
        default=False,
        description="When true, enqueue a persistent tool workflow instead of chat gateway.",
    )
    channel: str | None = Field(
        default=None,
        description="Channel for runtime session binding (web, api, telegram, …).",
    )

    def resolved_text(self) -> str:
        return str(self.text or self.raw or self.message or self.prompt or "").strip()

    def resolved_user_id(self) -> str:
        return str(self.user_id or "dev_user").strip()

    def resolved_channel(self) -> str:
        return str(self.channel or "web").strip() or "web"


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
def mission_control_summary_deprecated() -> None:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Removed — use GET /api/v1/mission-control/state (single Mission Control payload).",
    )


@router.get("/state")
def mission_control_state(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
    hours: int = Query(24, ge=1, le=168, description="Trust/dashboard look-back window (hours)"),
) -> dict:
    """Unified Mission Control state — execution snapshot plus orchestration/trust dashboard."""
    return build_execution_snapshot(db, user_id=app_user_id, hours=hours)


@router.post("/autonomy/tasks/{task_id}/interrupt")
def mission_control_interrupt_autonomous_task(
    task_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    """Phase 44 — mark an autonomous queued task as interrupted (logged + feedback row)."""
    tid = (task_id or "").strip()
    if not tid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="empty task id")
    row = db.get(NexaAutonomousTask, tid)
    if row is None or row.user_id != app_user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    if row.state in ("completed", "interrupted", "cancelled"):
        return {"ok": True, "task_id": tid, "state": row.state, "idempotent": True}
    row.state = "interrupted"
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    record_task_feedback(
        db,
        user_id=app_user_id,
        task_id=tid,
        outcome="fail",
        reason="user_interrupt",
        meta={"via": "mission_control"},
    )
    audit(
        db,
        event_type="mission_control.autonomy.task.interrupted",
        actor="aethos",
        user_id=app_user_id,
        message=f"Interrupted autonomous task {tid}",
        metadata={"task_id": tid},
    )
    return {"ok": True, "task_id": tid, "state": row.state}


@router.post("/override-alert")
def mission_control_override_alert(
    body: IntegrityOverrideBody,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    """Phase 19 — dismiss warning-level integrity alerts (secrets / critical cannot be overridden)."""
    try:
        return apply_integrity_alert_override(body.alert_id, body.action, user_id=app_user_id)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/export/{mission_id}")
def mission_control_export_mission(
    mission_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    """Export one mission with tasks and artifacts as JSON (Phase 20)."""
    bundle = export_mission_bundle(db, mission_id=mission_id, user_id=app_user_id)
    if not bundle:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return bundle


@router.post("/import")
def mission_control_import_mission(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    """Import a previously exported mission bundle (new mission id)."""
    if not isinstance(payload, dict) or not isinstance(payload.get("mission"), dict):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Expected bundle shape with top-level 'mission' object",
        )
    return import_mission_bundle(db, user_id=app_user_id, bundle=payload)


@router.get("/graph")
def mission_control_graph(
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
    hours: int = Query(24, ge=1, le=168, description="Same dashboard window as /state"),
) -> dict:
    """Agent/task nodes and dependency edges for Mission Control visualization."""
    state = build_execution_snapshot(db, user_id=app_user_id, hours=hours)
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
    body: MissionControlGatewayRunBody,
    db: Session = Depends(get_db),
) -> dict:
    """Run user text through :class:`~app.services.gateway.runtime.NexaGateway`."""
    text = body.resolved_text()
    user_id = body.resolved_user_id()
    if not text:
        return {"mode": "chat", "text": "", "intent": "empty"}

    if body.workflow or text.lower().startswith("workflow:"):
        from app.execution.workflow_runner import persist_operator_workflow
        from app.runtime.runtime_state import load_runtime_state, save_runtime_state

        raw = text
        if raw.lower().startswith("workflow:"):
            raw = raw[len("workflow:") :].lstrip()
        st = load_runtime_state()
        out = persist_operator_workflow(st, raw, user_id=user_id, channel=body.resolved_channel())
        save_runtime_state(st)
        return {"mode": "workflow", **out}

    from app.services.gateway.context import GatewayContext
    from app.services.gateway.runtime import NexaGateway

    ctx = GatewayContext.from_channel(user_id, "web", {"via_gateway": True})
    return NexaGateway().handle_message(ctx, text, db=db)


@router.post("/replay/{mission_id}")
def mission_control_replay_mission(
    mission_id: str,
    db: Session = Depends(get_db),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    """Re-run stored mission input text through the gateway (same privacy guarantees)."""
    from app.services.gateway.context import GatewayContext
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
    ctx = GatewayContext.from_channel(app_user_id, "web", {"via_gateway": True})
    out = NexaGateway().handle_message(ctx, raw, db=db)
    if isinstance(out, dict) and not any(k in out for k in ("mode", "text", "ok")):
        return {**out, "ok": True}
    return out


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
        actor="aethos",
        user_id=app_user_id,
        message=f"Dismissed attention item {iid}",
        metadata={"attention_id": iid},
    )
    return {"ok": True, "attention_id": iid, "dismissed": True}
