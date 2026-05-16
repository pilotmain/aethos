# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Task → workflow → agent → provider ownership chains (Phase 2 Step 9)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_state import load_runtime_state


def build_ownership_chains(user_id: str | None = None) -> list[dict[str, Any]]:
    st = load_runtime_state()
    uid = (user_id or "").strip()
    chains: list[dict[str, Any]] = []
    registry = st.get("task_registry") or {}
    agents = st.get("runtime_agents") or {}
    if not isinstance(registry, dict):
        return chains
    for tid, task in list(registry.items())[:40]:
        if not isinstance(task, dict):
            continue
        if uid and str(task.get("user_id") or "") != uid:
            continue
        agent_id = task.get("assigned_agent_id") or task.get("assigned_runtime_agent_id")
        agent_row = agents.get(agent_id) if isinstance(agents, dict) and agent_id else None
        chains.append(
            {
                "task_id": str(tid),
                "workflow_id": task.get("execution_plan_id") or task.get("workflow_id"),
                "runtime_agent_id": agent_id,
                "provider": (agent_row or {}).get("provider") if isinstance(agent_row, dict) else task.get("provider"),
                "model": (agent_row or {}).get("model") if isinstance(agent_row, dict) else None,
                "state": task.get("state"),
                "delegation": task.get("delegation_chain") or [],
                "recovery_owner": task.get("recovery_owner"),
                "retry_owner": task.get("retry_owner") or agent_id,
            }
        )
    return chains
