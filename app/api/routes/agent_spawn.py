"""
REST API for orchestration sub-agents (spawn / list / CRUD / CEO lifecycle).

Uses the same web chat scope as the gateway: ``web:{user_id}:default``.
Requires ``X-User-Id`` (+ optional bearer when ``NEXA_WEB_API_TOKEN`` is set).
Ids are validated via :func:`~app.services.web_user_id.validate_web_user_id` (e.g. ``telegram_<digits>`` → ``tg_<digits>``).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import get_valid_web_user_id
from app.services.agent.activity_tracker import get_activity_tracker
from app.services.sub_agent_registry import AgentRegistry, AgentStatus

router = APIRouter(prefix="/agents", tags=["agents"])


def _web_chat_scope(app_user_id: str, session_id: str = "default") -> str:
    uid = (app_user_id or "").strip()[:128]
    sid = (session_id or "default").strip()[:64]
    return f"web:{uid}:{sid}"


class SpawnAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    domain: str = Field(..., min_length=1, max_length=64)
    skills: list[str] | None = None


class CreateAgentRequest(BaseModel):
    """Spawn a full-capability orchestration agent (same registry as ``/spawn``)."""

    name: str = Field(..., min_length=1, max_length=120)
    domain: str = Field(..., min_length=1, max_length=64)
    skills: list[str] | None = None
    auto_approve: bool = False


class UpdateAgentRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    domain: str | None = Field(None, min_length=1, max_length=64)
    skills: list[str] | None = None
    status: str | None = None
    auto_approve: bool | None = None


def _agent_payload(agent: Any, *, include_stats: bool = False) -> dict[str, Any]:
    from datetime import datetime, timezone

    md = dict(getattr(agent, "metadata", None) or {})
    cur = md.get("current_task")
    la = getattr(agent, "last_active", None)
    last_active_iso = None
    if isinstance(la, (int, float)):
        last_active_iso = datetime.fromtimestamp(float(la), tz=timezone.utc).isoformat()
    ca = getattr(agent, "created_at", None)
    created_iso = None
    if isinstance(ca, (int, float)):
        created_iso = datetime.fromtimestamp(float(ca), tz=timezone.utc).isoformat()
    elif hasattr(ca, "isoformat"):
        created_iso = ca.isoformat()

    out: dict[str, Any] = {
        "id": agent.id,
        "name": agent.name,
        "domain": agent.domain,
        "status": agent.status.value,
        "skills": list(agent.capabilities or []),
        "capabilities": list(agent.capabilities or []),
        "current_task": cur,
        "last_active": last_active_iso,
        "created_at": created_iso,
        "auto_approve": bool(getattr(agent, "trusted", False)),
    }
    if include_stats:
        st = get_activity_tracker().get_agent_statistics(agent.id)
        out.update(
            {
                "total_tasks": int(st.get("total_tasks", 0) or 0),
                "successful_tasks": int(st.get("successful_actions", 0) or 0),
                "failed_tasks": int(st.get("failed_actions", 0) or 0),
                "success_rate": float(st.get("success_rate", 100.0) or 100.0),
                "total_actions": int(st.get("total_actions", 0) or 0),
            }
        )
    return out


def _ensure_agent(agent_id: str, chat_id: str):
    registry = AgentRegistry()
    agent = registry.get_agent(agent_id)
    if not agent or agent.parent_chat_id != chat_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return registry, agent


def _orch_enabled() -> None:
    if not bool(getattr(get_settings(), "nexa_agent_orchestration_enabled", False)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent orchestration is disabled (set NEXA_AGENT_ORCHESTRATION_ENABLED=true).",
        )


@router.post("/spawn")
def post_spawn_agent(
    body: SpawnAgentRequest,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Spawn (register) a sub-agent for the authenticated user's web orchestration scope."""
    _orch_enabled()

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


@router.post("/create")
def post_create_agent(
    body: CreateAgentRequest,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Create an orchestration sub-agent (trusted flag follows ``auto_approve`` + defaults)."""
    _orch_enabled()
    settings = get_settings()
    chat_id = _web_chat_scope(app_user_id)
    registry = AgentRegistry()
    name_key = body.name.strip()
    if registry.get_agent_by_name(name_key, chat_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent '{name_key}' already exists for this workspace.",
        )

    default_trusted = bool(getattr(settings, "nexa_agent_auto_approve", False))
    trusted = bool(body.auto_approve or default_trusted)
    caps = list(body.skills) if body.skills else None

    agent = registry.spawn_agent(
        name_key,
        body.domain.strip().lower(),
        chat_id,
        capabilities=caps,
        trusted=trusted,
    )
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create agent (limit reached or orchestration blocked).",
        )

    get_activity_tracker().log_action(
        agent_id=agent.id,
        agent_name=agent.name,
        action_type="created",
        metadata={"by_scope": chat_id, "trusted": trusted},
    )

    return {
        "ok": True,
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "domain": agent.domain,
            "status": agent.status.value,
            "skills": list(agent.capabilities or []),
            "auto_approve": trusted,
        },
    }


@router.get("/list")
def get_agents_list(
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    chat_id = _web_chat_scope(app_user_id)
    agents = AgentRegistry().list_agents(chat_id)
    return {"ok": True, "agents": [_agent_payload(a, include_stats=True) for a in agents], "count": len(agents)}


@router.get("/by-id/{agent_id}")
def get_agent_by_id(
    agent_id: str,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    chat_id = _web_chat_scope(app_user_id)
    _, agent = _ensure_agent(agent_id, chat_id)
    return {"ok": True, "agent": _agent_payload(agent, include_stats=True)}


@router.patch("/by-id/{agent_id}")
def patch_agent_by_id(
    agent_id: str,
    body: UpdateAgentRequest,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _orch_enabled()
    chat_id = _web_chat_scope(app_user_id)
    registry, agent = _ensure_agent(agent_id, chat_id)

    changes = body.model_dump(exclude_unset=True)
    if body.name is not None:
        other = registry.get_agent_by_name(body.name.strip(), chat_id)
        if other and other.id != agent_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Name already in use")

    new_status: AgentStatus | None = None
    if body.status is not None:
        raw = body.status.strip().lower()
        try:
            new_status = AgentStatus(raw)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status: {raw}",
            ) from exc

    name = body.name.strip() if body.name is not None else None
    domain = body.domain.strip().lower() if body.domain is not None else None
    caps = list(body.skills) if body.skills is not None else None
    trusted = body.auto_approve if body.auto_approve is not None else None

    if new_status == AgentStatus.TERMINATED:
        registry.patch_agent(
            agent_id,
            name=name,
            domain=domain,
            capabilities=caps,
            trusted=trusted,
        )
        registry.terminate_agent(agent_id)
    elif new_status is not None:
        registry.patch_agent(
            agent_id,
            name=name,
            domain=domain,
            capabilities=caps,
            trusted=trusted,
            status=new_status,
        )
    else:
        registry.patch_agent(
            agent_id,
            name=name,
            domain=domain,
            capabilities=caps,
            trusted=trusted,
        )

    fresh = registry.get_agent(agent_id)
    assert fresh is not None

    get_activity_tracker().log_action(
        agent_id=fresh.id,
        agent_name=fresh.name,
        action_type="updated",
        metadata={"changes": changes},
    )

    return {"ok": True, "agent": {"id": fresh.id, "name": fresh.name, "status": fresh.status.value}}


@router.delete("/by-id/{agent_id}")
def delete_agent_by_id(
    agent_id: str,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _orch_enabled()
    chat_id = _web_chat_scope(app_user_id)
    registry, agent = _ensure_agent(agent_id, chat_id)

    get_activity_tracker().log_action(
        agent_id=agent.id,
        agent_name=agent.name,
        action_type="deleted",
        metadata={"domain": agent.domain, "scope": chat_id},
    )

    if not registry.remove_agent(agent_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    return {"ok": True, "message": f"Agent '{agent.name}' deleted"}


@router.post("/by-id/{agent_id}/pause")
def pause_agent_by_id(
    agent_id: str,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _orch_enabled()
    chat_id = _web_chat_scope(app_user_id)
    registry, agent = _ensure_agent(agent_id, chat_id)
    registry.patch_agent(agent_id, status=AgentStatus.PAUSED)
    get_activity_tracker().log_action(agent_id=agent.id, agent_name=agent.name, action_type="paused")
    return {"ok": True, "message": f"Agent '{agent.name}' paused"}


@router.post("/by-id/{agent_id}/resume")
def resume_agent_by_id(
    agent_id: str,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    _orch_enabled()
    chat_id = _web_chat_scope(app_user_id)
    registry, agent = _ensure_agent(agent_id, chat_id)
    if agent.status == AgentStatus.TERMINATED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot resume a terminated agent")
    registry.patch_agent(agent_id, status=AgentStatus.IDLE)
    get_activity_tracker().log_action(agent_id=agent.id, agent_name=agent.name, action_type="resumed")
    return {"ok": True, "message": f"Agent '{agent.name}' resumed"}


@router.get("/status/{agent_name}")
def get_agent_named_status(
    agent_name: str,
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    chat_id = _web_chat_scope(app_user_id)
    agent = AgentRegistry().get_agent_by_name(agent_name.strip(), chat_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_name}' not found")
    return {"ok": True, "agent": _agent_payload(agent, include_stats=True)}


__all__ = ["router", "_agent_payload", "_web_chat_scope"]
