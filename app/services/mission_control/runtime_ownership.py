# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Task → workflow → agent → provider ownership chains (Phase 2 Step 9–10)."""

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


def build_operator_trace_chains(user_id: str | None = None) -> list[dict[str, Any]]:
    """Full operator trace: task → agent → provider → deployment → verification."""
    st = load_runtime_state()
    uid = (user_id or "").strip()
    repairs = st.get("repair_contexts") or {}
    latest_repairs = repairs.get("latest_by_project") if isinstance(repairs, dict) else {}
    traces: list[dict[str, Any]] = []

    for chain in build_ownership_chains(user_id):
        traces.append(
            {
                **chain,
                "trace": [
                    {"step": "task", "id": chain.get("task_id")},
                    {"step": "workflow", "id": chain.get("workflow_id")},
                    {"step": "runtime_agent", "id": chain.get("runtime_agent_id")},
                    {"step": "provider", "id": chain.get("provider"), "model": chain.get("model")},
                ],
            }
        )

    if isinstance(latest_repairs, dict):
        for pid, rid in list(latest_repairs.items())[:16]:
            bucket = repairs.get(pid) if isinstance(repairs.get(pid), dict) else {}
            row = bucket.get(rid) if isinstance(bucket, dict) and isinstance(rid, str) else None
            if not isinstance(row, dict):
                continue
            traces.append(
                {
                    "task_id": f"repair:{pid}",
                    "workflow_id": row.get("plan_id"),
                    "runtime_agent_id": (row.get("brain_decision") or {}).get("selected_provider"),
                    "provider": row.get("provider") or "vercel",
                    "repair_context_id": row.get("repair_context_id"),
                    "verification": row.get("verification_result"),
                    "deployment": row.get("deploy_result"),
                    "trace": [
                        {"step": "repair", "project_id": pid},
                        {"step": "brain", "id": (row.get("brain_decision") or {}).get("selected_model")},
                        {"step": "verification", "ok": (row.get("verification_result") or {}).get("verified")},
                        {"step": "deployment", "status": row.get("status")},
                    ],
                }
            )
    return traces[:32]
