# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Coordination agent HTTP API (OpenClaw multi-agent parity).

Routes live under ``/api/v1/runtime/agents/*`` so ``GET /api/v1/agents`` remains absent (Phase 27
contract — orchestration spawn stays on ``/api/v1/agents/list``, ``/spawn``, …).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.agent_coordination import list_tasks_for_agent
from app.agents.agent_delegation import list_delegations_for_agent
from app.agents.agent_registry import get_agent, list_agents_for_user
from app.core.security import get_valid_web_user_id
from app.runtime.runtime_state import load_runtime_state

router = APIRouter(prefix="/runtime/agents", tags=["agent-coordination"])


def _belongs(row: dict[str, Any], app_user_id: str) -> bool:
    return str(row.get("user_id") or "") == str(app_user_id)


@router.get("/")
def list_agents(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    rows = list_agents_for_user(st, app_user_id)
    return {"agents": rows, "count": len(rows)}


@router.get("/{agent_id}")
def get_agent_detail(agent_id: str, app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    row = get_agent(st, agent_id)
    if not row or not _belongs(row, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return {"agent": row}


@router.get("/{agent_id}/tasks")
def get_agent_tasks(agent_id: str, app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    row = get_agent(st, agent_id)
    if not row or not _belongs(row, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agent not found")
    tasks = list_tasks_for_agent(st, agent_id, app_user_id)
    return {"agent_id": agent_id, "tasks": tasks, "count": len(tasks)}


@router.get("/{agent_id}/delegations")
def get_agent_delegations(agent_id: str, app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    st = load_runtime_state()
    row = get_agent(st, agent_id)
    if not row or not _belongs(row, app_user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agent not found")
    dels = list_delegations_for_agent(st, agent_id)
    return {"agent_id": agent_id, "delegations": dels, "count": len(dels)}
