# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Unified orchestration agent list for Mission Control (web + Telegram scopes).

Uses :meth:`~app.services.sub_agent_registry.AgentRegistry.list_agents_for_app_user` —
same roster as ``GET /api/v1/agents/list`` and ``GET /api/v1/ceo/dashboard``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.routes.agent_spawn import _agent_payload
from app.core.security import get_valid_web_user_id
from app.services.sub_agent_registry import AgentRegistry

router = APIRouter(prefix="/mission", tags=["mission"])


def _creation_source(parent_chat_id: str) -> str:
    pc = parent_chat_id or ""
    if pc.startswith("web:"):
        return "web"
    if pc.startswith("telegram:") or pc.startswith("telegram:user:"):
        return "telegram"
    if pc.startswith("tg_"):
        return "telegram"
    return "other"


@router.get("/agents")
def get_mission_agents(app_user_id: str = Depends(get_valid_web_user_id)) -> dict[str, Any]:
    reg = AgentRegistry()
    agents = reg.list_agents_for_app_user(app_user_id)
    rows: list[dict[str, Any]] = []
    n_web = n_tg = n_other = 0
    for a in agents:
        payload = _agent_payload(a, include_stats=True)
        src = _creation_source(a.parent_chat_id)
        payload["source"] = src
        if src == "web":
            n_web += 1
        elif src == "telegram":
            n_tg += 1
        else:
            n_other += 1
        rows.append(payload)

    return {
        "ok": True,
        "agents": rows,
        "count": len(rows),
        "sources": {"web": n_web, "telegram": n_tg, "other": n_other},
    }


__all__ = ["router"]
