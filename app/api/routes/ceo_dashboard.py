"""
CEO dashboard JSON API — orchestration agents scoped to the authenticated web user.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.security import get_valid_web_user_id
from app.services.agent.activity_tracker import get_activity_tracker
from app.services.agent.supervisor import get_supervisor
from app.services.sub_agent_registry import AgentRegistry

from app.api.routes.agent_spawn import _agent_payload, _web_chat_scope

router = APIRouter(prefix="/ceo", tags=["ceo"])


def _scope_chat(app_user_id: str) -> str:
    return _web_chat_scope(app_user_id)


def _ensure_agent(agent_id: str, chat_id: str):
    registry = AgentRegistry()
    agent = registry.get_agent(agent_id)
    if not agent or agent.parent_chat_id != chat_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return registry, agent


class InterveneRequest(BaseModel):
    correction: str = Field(..., min_length=1, max_length=8000)


class RedirectRequest(BaseModel):
    new_task: str = Field(..., min_length=1, max_length=8000)


@router.get("/dashboard")
def get_ceo_dashboard(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    chat_id = _scope_chat(app_user_id)
    registry = AgentRegistry()
    tracker = get_activity_tracker()
    agents = registry.list_agents(chat_id)
    agent_ids = [a.id for a in agents]

    agent_insights: list[dict[str, Any]] = []
    actions_weights: list[tuple[float, int]] = []

    for agent in agents:
        stats = tracker.get_agent_statistics(agent.id)
        tr = float(stats.get("success_rate", 100.0) or 100.0)
        ta = int(stats.get("total_actions", 0) or 0)
        rates.append(tr)
        actions_weights.append((tr, ta))
        payload = _agent_payload(agent)
        payload.update(
            {
                "total_actions": ta,
                "success_rate": tr,
                "successful_tasks": int(stats.get("successful_actions", 0) or 0),
                "failed_tasks": int(stats.get("failed_actions", 0) or 0),
            }
        )
        agent_insights.append(payload)

    total_actions_today = tracker.count_actions_today(agent_ids)
    overall = 100.0
    tw = sum(w for _, w in actions_weights)
    if tw > 0:
        overall = round(sum(r * w for r, w in actions_weights) / tw, 1)

    summary = {
        "total_agents": len(agents),
        "active_agents": len([a for a in agents if a.status.value == "idle"]),
        "busy_agents": len([a for a in agents if a.status.value == "busy"]),
        "paused_agents": len([a for a in agents if a.status.value == "paused"]),
        "total_actions_today": total_actions_today,
        "overall_success_rate": overall,
    }

    return {"ok": True, "agents": agent_insights, "summary": summary}


@router.get("/agent/{agent_id}/insights")
async def get_agent_insights_route(
    agent_id: str,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    chat_id = _scope_chat(app_user_id)
    _ensure_agent(agent_id, chat_id)
    supervisor = get_supervisor()
    insights = await supervisor.get_agent_insights(agent_id)
    if "error" in insights:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=insights["error"])
    return {"ok": True, "insights": insights}


@router.post("/agent/{agent_id}/intervene")
async def intervene_route(
    agent_id: str,
    body: InterveneRequest,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    chat_id = _scope_chat(app_user_id)
    _ensure_agent(agent_id, chat_id)
    supervisor = get_supervisor()
    result = await supervisor.intervene(agent_id, body.correction)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])
    return {"ok": True, "message": result["message"]}


@router.post("/agent/{agent_id}/redirect")
async def redirect_route(
    agent_id: str,
    body: RedirectRequest,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    chat_id = _scope_chat(app_user_id)
    _ensure_agent(agent_id, chat_id)
    supervisor = get_supervisor()
    result = await supervisor.redirect_agent(agent_id, body.new_task)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])
    return {"ok": True, "message": result["message"]}


@router.get("/activity")
def get_activity_feed(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=500),
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    chat_id = _scope_chat(app_user_id)
    agents = AgentRegistry().list_agents(chat_id)
    ids = [a.id for a in agents]
    tracker = get_activity_tracker()
    activities = tracker.get_global_activity(ids, hours=hours, limit=limit)
    return {"ok": True, "activities": activities, "count": len(activities)}


__all__ = ["router"]
