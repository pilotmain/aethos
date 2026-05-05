"""
REST API for orchestration sub-agents (spawn / list / status).

Uses the same web chat scope as the gateway: ``web:{user_id}:default``.
Requires ``X-User-Id`` (+ optional bearer when ``NEXA_WEB_API_TOKEN`` is set).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import get_valid_web_user_id
from app.services.sub_agent_registry import AgentRegistry

router = APIRouter(prefix="/agents", tags=["agents"])


def _web_chat_scope(app_user_id: str, session_id: str = "default") -> str:
    uid = (app_user_id or "").strip()[:128]
    sid = (session_id or "default").strip()[:64]
    return f"web:{uid}:{sid}"


class SpawnAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    domain: str = Field(..., min_length=1, max_length=64)
    skills: list[str] | None = None


def _agent_payload(agent: Any) -> dict[str, Any]:
    md = dict(getattr(agent, "metadata", None) or {})
    cur = md.get("current_task")
    la = getattr(agent, "last_active", None)
    last_active_iso = None
    if isinstance(la, (int, float)):
        from datetime import datetime, timezone

        last_active_iso = datetime.fromtimestamp(float(la), tz=timezone.utc).isoformat()
    ca = getattr(agent, "created_at", None)
    created_iso = ca.isoformat() if hasattr(ca, "isoformat") else None
    return {
        "id": agent.id,
        "name": agent.name,
        "domain": agent.domain,
        "status": agent.status.value,
        "capabilities": list(agent.capabilities or []),
        "current_task": cur,
        "last_active": last_active_iso,
        "created_at": created_iso,
    }


@router.post("/spawn")
def post_spawn_agent(
    body: SpawnAgentRequest,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Spawn (register) a sub-agent for the authenticated user's web orchestration scope."""
    if not bool(getattr(get_settings(), "nexa_agent_orchestration_enabled", False)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent orchestration is disabled (set NEXA_AGENT_ORCHESTRATION_ENABLED=true).",
        )

    chat_id = _web_chat_scope(app_user_id)
    registry = AgentRegistry()
    existing = registry.get_agent_by_name(body.name.strip(), chat_id)
    if existing:
        return {
            "ok": True,
            "agent": {"id": existing.id, "name": existing.name, "domain": existing.domain},
            "message": "Agent already exists for this session",
        }

    caps = list(body.skills) if body.skills else None
    agent = registry.spawn_agent(
        body.name.strip(),
        body.domain.strip().lower(),
        chat_id,
        capabilities=caps,
    )
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to spawn agent (limit reached, duplicate name, or orchestration blocked).",
        )

    return {"ok": True, "agent": {"id": agent.id, "name": agent.name, "domain": agent.domain}}


@router.get("/list")
def get_agents_list(
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    chat_id = _web_chat_scope(app_user_id)
    agents = AgentRegistry().list_agents(chat_id)
    return {"ok": True, "agents": [_agent_payload(a) for a in agents]}


@router.get("/status/{agent_name}")
def get_agent_named_status(
    agent_name: str,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    chat_id = _web_chat_scope(app_user_id)
    agent = AgentRegistry().get_agent_by_name(agent_name.strip(), chat_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_name}' not found")
    return {"ok": True, "agent": _agent_payload(agent)}


__all__ = ["router"]
