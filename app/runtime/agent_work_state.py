# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Tracked agent tasks, outputs, and registry ↔ runtime worker links (Phase 3 Step 6)."""

from __future__ import annotations

import uuid
from typing import Any

from app.orchestration.task_registry import put_task, update_task_state
from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso


def ensure_agent_work_schema(st: dict[str, Any]) -> None:
    if not isinstance(st.get("agent_outputs"), dict):
        st["agent_outputs"] = {}
    if not isinstance(st.get("runtime_agent_handles"), dict):
        st["runtime_agent_handles"] = {}


def normalize_handle(name: str) -> str:
    h = (name or "").strip().lstrip("@").lower()
    if h and not h.endswith("_agent"):
        return f"{h}_agent"
    return h


def handle_at(name: str) -> str:
    return f"@{normalize_handle(name)}"


def link_registry_agent_to_runtime(
    *,
    registry_agent_id: str,
    name: str,
    domain: str,
    created_by: str = "aethos_orchestrator",
) -> dict[str, Any]:
    """Create or refresh a runtime worker row for an orchestration sub-agent."""
    from app.runtime.runtime_agents import spawn_runtime_agent, touch_runtime_agent

    h = normalize_handle(name)
    st = load_runtime_state()
    ensure_agent_work_schema(st)
    handles = st["runtime_agent_handles"]
    existing_id = handles.get(h) if isinstance(handles, dict) else None
    agents = st.get("runtime_agents") or {}
    if existing_id and isinstance(agents, dict) and existing_id in agents:
        row = dict(agents[existing_id])
        row["handle"] = handle_at(name)
        row["display_name"] = name.replace("_", " ").title()
        row["registry_agent_id"] = registry_agent_id
        row["role"] = domain
        row["agent_type"] = domain
        row["created_by"] = created_by
        row["runtime_managed"] = True
        row.setdefault("history", [])
        row.setdefault("latest_artifact_ids", [])
        agents[existing_id] = row
        st["runtime_agents"] = agents
        save_runtime_state(st)
        touch_runtime_agent(str(existing_id), status="idle")
        return row

    row = spawn_runtime_agent(
        agent_type=domain or "general",
        created_from_task=f"registry:{registry_agent_id}",
        provider="orchestrator",
        model="sub_agent",
        ttl_sec=86400 * 7,
    )
    aid = str(row["agent_id"])
    row = dict(row)
    row["handle"] = handle_at(name)
    row["display_name"] = name.replace("_", " ").title()
    row["registry_agent_id"] = registry_agent_id
    row["created_by"] = created_by
    row["created_at"] = utc_now_iso()
    row["current_task_id"] = None
    row["latest_output_id"] = None
    row["latest_artifact_ids"] = []
    row["history"] = []
    agents = st.get("runtime_agents") or {}
    if isinstance(agents, dict):
        agents[aid] = row
        st["runtime_agents"] = agents
    handles[h] = aid
    st["runtime_agent_handles"] = handles
    save_runtime_state(st)
    try:
        from app.services.mission_control.mc_runtime_events import emit_mc_runtime_event

        emit_mc_runtime_event(
            "agent_created",
            agent_id=aid,
            handle=row["handle"],
            role=domain,
            registry_agent_id=registry_agent_id,
        )
    except Exception:
        pass
    return row


def find_runtime_agent_by_handle(handle: str) -> dict[str, Any] | None:
    h = normalize_handle(handle)
    st = load_runtime_state()
    ensure_agent_work_schema(st)
    handles = st.get("runtime_agent_handles") or {}
    aid = handles.get(h) if isinstance(handles, dict) else None
    if not aid:
        for aid2, row in (st.get("runtime_agents") or {}).items():
            if isinstance(row, dict) and normalize_handle(str(row.get("handle") or "")) == h:
                aid = aid2
                break
    if not aid:
        return None
    row = (st.get("runtime_agents") or {}).get(aid)
    return dict(row, agent_id=aid) if isinstance(row, dict) else None


def find_runtime_agent_by_registry_id(registry_agent_id: str) -> dict[str, Any] | None:
    st = load_runtime_state()
    for aid, row in (st.get("runtime_agents") or {}).items():
        if isinstance(row, dict) and str(row.get("registry_agent_id") or "") == registry_agent_id:
            return dict(row, agent_id=aid)
    return None


def create_agent_task(
    *,
    runtime_agent_id: str,
    agent_handle: str,
    prompt: str,
    registry_agent_id: str | None = None,
) -> str:
    st = load_runtime_state()
    ensure_agent_work_schema(st)
    task_id = f"atask_{uuid.uuid4().hex[:12]}"
    task = {
        "id": task_id,
        "task_id": task_id,
        "assigned_agent_id": runtime_agent_id,
        "agent_handle": handle_at(agent_handle),
        "state": "running",
        "status": "running",
        "prompt": (prompt or "")[:4000],
        "outputs": [],
        "artifacts": [],
        "created_by": "aethos_orchestrator",
        "registry_agent_id": registry_agent_id,
        "created_at": utc_now_iso(),
    }
    put_task(st, task)
    agents = st.get("runtime_agents") or {}
    row = agents.get(runtime_agent_id) if isinstance(agents, dict) else None
    if isinstance(row, dict):
        row = dict(row)
        row["current_task_id"] = task_id
        row["status"] = "busy"
        row["lifecycle"] = "busy"
        row["assignment"] = {"task_id": task_id, "prompt": prompt[:200]}
        agents[runtime_agent_id] = row
        st["runtime_agents"] = agents
    save_runtime_state(st)
    from app.runtime.runtime_agents import assign_runtime_agent

    assign_runtime_agent(runtime_agent_id, task_id=task_id)
    return task_id


def record_agent_output(
    *,
    runtime_agent_id: str,
    task_id: str,
    summary: str,
    content: str,
    artifacts: list[str] | None = None,
    status: str = "final",
    success: bool = True,
) -> str:
    st = load_runtime_state()
    ensure_agent_work_schema(st)
    output_id = f"aout_{uuid.uuid4().hex[:12]}"
    out_row = {
        "output_id": output_id,
        "task_id": task_id,
        "agent_id": runtime_agent_id,
        "summary": (summary or "")[:500],
        "content": (content or "")[:12000],
        "artifacts": list(artifacts or [])[:24],
        "created_at": utc_now_iso(),
        "status": status,
        "success": success,
    }
    outputs = st.setdefault("agent_outputs", {})
    if isinstance(outputs, dict):
        outputs[output_id] = out_row
    update_task_state(
        st,
        task_id,
        "completed" if success else "failed",
        latest_output_id=output_id,
        result_summary=summary[:500],
    )
    task = (st.get("task_registry") or {}).get(task_id)
    if isinstance(task, dict):
        task_outputs = task.setdefault("outputs", [])
        if isinstance(task_outputs, list):
            task_outputs.append(output_id)
    agents = st.get("runtime_agents") or {}
    row = agents.get(runtime_agent_id) if isinstance(agents, dict) else None
    if isinstance(row, dict):
        row = dict(row)
        row["latest_output_id"] = output_id
        row["current_task_id"] = None if success else task_id
        row["status"] = "idle" if success else "failed"
        row["lifecycle"] = row["status"]
        row["assignment"] = None if success else row.get("assignment")
        hist = list(row.get("history") or [])
        hist.append(
            {
                "at": utc_now_iso(),
                "task_id": task_id,
                "output_id": output_id,
                "status": "completed" if success else "failed",
                "summary": summary[:200],
            }
        )
        row["history"] = hist[-32:]
        agents[runtime_agent_id] = row
        st["runtime_agents"] = agents
    save_runtime_state(st)
    if success:
        from app.runtime.runtime_agents import release_runtime_agent

        release_runtime_agent(runtime_agent_id)
    return output_id


def list_tasks_for_agent(runtime_agent_id: str, *, limit: int = 8) -> list[dict[str, Any]]:
    st = load_runtime_state()
    out: list[dict[str, Any]] = []
    for tid, task in (st.get("task_registry") or {}).items():
        if not isinstance(task, dict):
            continue
        if str(task.get("assigned_agent_id") or "") == runtime_agent_id:
            out.append({**task, "task_id": tid})
    out.sort(key=lambda t: str(t.get("created_at") or ""), reverse=True)
    return out[:limit]


def get_output(output_id: str) -> dict[str, Any] | None:
    st = load_runtime_state()
    row = (st.get("agent_outputs") or {}).get(output_id)
    return dict(row) if isinstance(row, dict) else None
