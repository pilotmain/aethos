# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime worker clarity for Mission Control (Phase 3 Step 4)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_agents import ORCHESTRATOR_ID, list_runtime_agents
from app.services.mission_control.runtime_ownership import build_ownership_chains


def build_runtime_workers_view(user_id: str | None = None) -> dict[str, Any]:
    agents = list_runtime_agents(include_expired=False)
    chains = {c.get("runtime_agent_id"): c for c in build_ownership_chains(user_id) if c.get("runtime_agent_id")}
    workers: list[dict[str, Any]] = []
    orchestrator: dict[str, Any] | None = None
    for aid, row in agents.items():
        if not isinstance(row, dict):
            continue
        chain = chains.get(aid) or {}
        enriched = {
            "agent_id": aid,
            "handle": row.get("handle"),
            "display_name": row.get("display_name"),
            "role": row.get("role") or row.get("agent_type"),
            "persistent": bool(row.get("persistent")),
            "status": row.get("status") or row.get("lifecycle"),
            "provider": row.get("provider"),
            "model": row.get("model"),
            "assignment": row.get("assignment"),
            "current_task_id": row.get("current_task_id"),
            "latest_output_id": row.get("latest_output_id"),
            "created_by": row.get("created_by"),
            "last_activity": row.get("last_activity"),
            "ownership_chain": {
                "task_id": chain.get("task_id"),
                "workflow_id": chain.get("workflow_id"),
                "provider": chain.get("provider"),
            },
            "summary": _worker_summary(row, chain),
        }
        if aid == ORCHESTRATOR_ID or row.get("system"):
            orchestrator = enriched
        else:
            workers.append(enriched)
    return {
        "orchestrator": orchestrator,
        "workers": workers,
        "active_count": len([w for w in workers if w.get("status") not in ("expired", "suspended", "failed")]),
    }


def _worker_summary(row: dict[str, Any], chain: dict[str, Any]) -> str:
    role = str(row.get("role") or "worker")
    task = (row.get("assignment") or {}).get("task_id") or chain.get("task_id")
    prov = row.get("provider") or chain.get("provider") or "—"
    if task:
        return f"{role} working on {task} via {prov}"
    return f"{role} idle · provider {prov}"
