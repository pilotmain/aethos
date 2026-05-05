"""
Mobile app HTTP + WebSocket API (Phase 30).

Uses JWT bearer tokens signed with :envvar:`NEXA_SECRET_KEY`.
Mission Control rows for mobile use ``team_scope`` = ``mobile:{user_id}``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.mobile_token import MobileTokenError, create_mobile_access_token, decode_mobile_access_token
from app.services.project import get_project_controller
from app.services.rbac.organization_service import OrganizationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mobile", tags=["mobile"])


def mobile_team_scope(user_id: str) -> str:
    return f"mobile:{user_id}"


async def require_mobile_user(
    authorization: str | None = Header(None, alias="Authorization"),
) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    raw = authorization[7:].strip()
    try:
        payload = decode_mobile_access_token(raw)
        return str(payload["sub"])
    except MobileTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None


class LoginRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=256)
    user_name: str | None = Field(None, max_length=256)


@router.post("/auth/login")
async def mobile_login(body: LoginRequest) -> dict[str, Any]:
    """Issue JWT and list RBAC workspaces (e.g. Telegram numeric id as ``user_id``)."""
    try:
        token = create_mobile_access_token(body.user_id, body.user_name)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    ttl = max(1, int(get_settings().nexa_mobile_token_ttl_hours or 168))
    org_svc = OrganizationService()
    orgs = org_svc.list_organizations_for_user(body.user_id)
    return {
        "token": token,
        "token_type": "Bearer",
        "expires_in_hours": ttl,
        "user": {"id": body.user_id, "name": body.user_name},
        "organizations": [{"id": o.id, "name": o.name, "slug": o.slug} for o in orgs],
    }


@router.get("/me")
async def mobile_me(user_id: str = Depends(require_mobile_user)) -> dict[str, Any]:
    return {"user_id": user_id}


class CreateOrgBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str | None = Field(None, max_length=120)


@router.get("/orgs")
async def list_mobile_orgs(user_id: str = Depends(require_mobile_user)) -> dict[str, Any]:
    org_svc = OrganizationService()
    orgs = org_svc.list_organizations_for_user(user_id)
    out: list[dict[str, Any]] = []
    for o in orgs:
        mem = org_svc.get_member(o.id, user_id)
        out.append(
            {
                "id": o.id,
                "name": o.name,
                "slug": o.slug,
                "role": mem.role.value if mem else None,
            }
        )
    active = org_svc.get_active_organization_id(user_id)
    return {"organizations": out, "active_organization_id": active}


@router.post("/orgs")
async def create_mobile_org(
    body: CreateOrgBody,
    user_id: str = Depends(require_mobile_user),
) -> dict[str, Any]:
    org_svc = OrganizationService()
    org = org_svc.create_organization(body.name, body.slug, user_id)
    return {"organization": {"id": org.id, "name": org.name, "slug": org.slug}}


def _require_org_member(org_svc: OrganizationService, org_id: str, user_id: str) -> None:
    if not org_svc.get_member(org_id, user_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not a member of this organization")


@router.post("/orgs/{org_id}/active")
async def set_active_org(
    org_id: str,
    user_id: str = Depends(require_mobile_user),
) -> dict[str, Any]:
    """Set user's active workspace (mirrors Telegram ``/org switch``)."""
    org_svc = OrganizationService()
    _require_org_member(org_svc, org_id, user_id)
    org_svc.set_active_organization_id(user_id, org_id)
    org = org_svc.get_organization(org_id)
    return {"ok": True, "active_organization_id": org_id, "slug": org.slug if org else None}


@router.get("/orgs/{org_id}/members")
async def mobile_org_members(
    org_id: str,
    user_id: str = Depends(require_mobile_user),
) -> dict[str, Any]:
    org_svc = OrganizationService()
    _require_org_member(org_svc, org_id, user_id)
    members = org_svc.list_members(org_id)
    return {
        "members": [
            {
                "id": m.id,
                "user_id": m.user_id,
                "user_name": m.user_name,
                "role": m.role.value,
            }
            for m in members
        ]
    }


@router.get("/orgs/{org_id}/projects")
async def mobile_org_projects(
    org_id: str,
    user_id: str = Depends(require_mobile_user),
) -> dict[str, Any]:
    org_svc = OrganizationService()
    _require_org_member(org_svc, org_id, user_id)
    ctrl = get_project_controller()
    scope = mobile_team_scope(user_id)
    projects = ctrl.list_projects(scope, organization_id=org_id)
    items: list[dict[str, Any]] = []
    for p in projects:
        tree = ctrl.build_mission_tree(p.id)
        prog = int(tree.get("project", {}).get("progress", 0) or 0)
        ts = tree.get("tasks", {})
        items.append(
            {
                "id": p.id,
                "name": p.name,
                "goal": p.goal,
                "status": p.status.value,
                "progress": prog,
                "tasks_done": ts.get("done", 0),
                "tasks_total": ts.get("total", 0),
            }
        )
    return {"projects": items}


class CreateProjectBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    goal: str = Field(..., min_length=1)
    organization_id: str | None = None


@router.post("/projects")
async def mobile_create_project(
    body: CreateProjectBody,
    user_id: str = Depends(require_mobile_user),
) -> dict[str, Any]:
    org_id = body.organization_id
    if org_id:
        org_svc = OrganizationService()
        _require_org_member(org_svc, org_id, user_id)
        if not org_svc.check_permission(org_id, user_id, "create_project"):
            raise HTTPException(403, detail="Cannot create projects in this workspace")
    ctrl = get_project_controller()
    scope = mobile_team_scope(user_id)
    p = ctrl.create_project(
        body.name,
        body.goal,
        scope,
        organization_id=org_id,
    )
    return {"project": {"id": p.id, "name": p.name, "goal": p.goal}}


@router.get("/projects/{project_id}/tree")
async def mobile_project_tree(
    project_id: str,
    user_id: str = Depends(require_mobile_user),
) -> dict[str, Any]:
    ctrl = get_project_controller()
    proj = ctrl.get_project(project_id)
    if not proj or proj.team_scope != mobile_team_scope(user_id):
        raise HTTPException(404, detail="Project not found")
    return ctrl.build_mission_tree(project_id)


class CreateTaskBody(BaseModel):
    title: str = Field(..., min_length=1)
    project_id: str | None = None
    description: str | None = None


@router.post("/tasks")
async def mobile_create_task(
    body: CreateTaskBody,
    user_id: str = Depends(require_mobile_user),
) -> dict[str, Any]:
    ctrl = get_project_controller()
    scope = mobile_team_scope(user_id)
    if body.project_id:
        proj = ctrl.get_project(body.project_id)
        if not proj or proj.team_scope != scope:
            raise HTTPException(404, detail="Project not found")
    t = ctrl.add_task(
        body.title,
        project_id=body.project_id,
        team_scope=scope if not body.project_id else None,
        description=body.description,
    )
    return {"task": {"id": t.id, "title": t.title, "status": t.status.value}}


@router.get("/orgs/{org_id}/budget-summary")
async def mobile_budget_summary(
    org_id: str,
    user_id: str = Depends(require_mobile_user),
) -> dict[str, Any]:
    org_svc = OrganizationService()
    _require_org_member(org_svc, org_id, user_id)
    return {
        "organization_id": org_id,
        "note": "Per-agent token budgets (Phase 28) require linked sub-agents; this summary is a placeholder.",
        "team_total_used": 0,
        "team_total_limit": 0,
    }


@router.websocket("/ws/chat")
async def mobile_chat_ws(
    websocket: WebSocket,
    token: str | None = Query(None),
) -> None:
    """Minimal authenticated JSON channel; extend to Nexa gateway streaming later."""
    await websocket.accept()
    if not token:
        await websocket.send_json({"type": "error", "message": "missing token query param"})
        await websocket.close(code=4401)
        return
    try:
        payload = decode_mobile_access_token(token)
        uid = str(payload["sub"])
    except MobileTokenError:
        await websocket.send_json({"type": "error", "message": "invalid token"})
        await websocket.close(code=4401)
        return
    await websocket.send_json({"type": "ready", "user_id": uid})
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"text": raw}
            await websocket.send_json(
                {
                    "type": "message",
                    "user_id": uid,
                    "echo": data,
                    "hint": "Gateway streaming can replace this echo path.",
                }
            )
    except WebSocketDisconnect:
        logger.debug("mobile ws disconnect user=%s", uid)


__all__ = ["router"]
