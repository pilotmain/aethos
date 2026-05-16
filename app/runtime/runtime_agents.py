# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Dynamic runtime agents — spawn, idle, suspend, expire (Phase 2 Step 8)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

ORCHESTRATOR_ID = "aethos_orchestrator"
ORCHESTRATOR_TYPE = "orchestrator"
_DEFAULT_TTL_SEC = 3600
_MAX_AGENTS = 128


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def ensure_runtime_agents_schema(st: dict[str, Any]) -> dict[str, Any]:
    ra = st.setdefault("runtime_agents", {})
    if not isinstance(ra, dict):
        st["runtime_agents"] = {}
        ra = st["runtime_agents"]
    orch = ra.get(ORCHESTRATOR_ID)
    if not isinstance(orch, dict):
        ra[ORCHESTRATOR_ID] = {
            "agent_id": ORCHESTRATOR_ID,
            "agent_type": ORCHESTRATOR_TYPE,
            "status": "active",
            "created_from_task": None,
            "provider": "aethos",
            "model": "orchestrator",
            "last_activity": utc_now_iso(),
            "expires_at": None,
            "runtime_managed": True,
            "system": True,
        }
    return ra


def list_runtime_agents(*, include_expired: bool = False) -> dict[str, Any]:
    st = load_runtime_state()
    ensure_runtime_agents_schema(st)
    sweep_expired_agents(st, persist=True)
    agents = st.get("runtime_agents") or {}
    out: dict[str, Any] = {}
    if isinstance(agents, dict):
        for aid, row in agents.items():
            if not isinstance(row, dict):
                continue
            if not include_expired and row.get("status") in ("expired", "suspended"):
                continue
            out[str(aid)] = dict(row)
    return out


def spawn_runtime_agent(
    *,
    agent_type: str,
    created_from_task: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    ttl_sec: int = _DEFAULT_TTL_SEC,
) -> dict[str, Any]:
    aid = f"agent_{uuid.uuid4().hex[:12]}"
    now = _now()
    expires = now + timedelta(seconds=max(60, int(ttl_sec)))
    row: dict[str, Any] = {
        "agent_id": aid,
        "agent_type": (agent_type or "general").strip().lower(),
        "status": "active",
        "created_from_task": created_from_task,
        "provider": (provider or "deterministic").strip().lower(),
        "model": (model or "").strip() or None,
        "last_activity": utc_now_iso(),
        "expires_at": expires.isoformat(),
        "runtime_managed": True,
        "system": False,
    }
    st = load_runtime_state()
    agents = ensure_runtime_agents_schema(st)
    agents[aid] = row
    _trim_agents(agents)
    save_runtime_state(st)
    try:
        from app.services.mission_control.mc_runtime_events import emit_mc_runtime_event

        emit_mc_runtime_event(
            "agent_spawned",
            agent_id=aid,
            agent_type=row["agent_type"],
            created_from_task=created_from_task,
        )
    except Exception:
        pass
    return row


def touch_runtime_agent(agent_id: str, *, status: str | None = None) -> dict[str, Any] | None:
    st = load_runtime_state()
    agents = ensure_runtime_agents_schema(st)
    row = agents.get(agent_id)
    if not isinstance(row, dict):
        return None
    row["last_activity"] = utc_now_iso()
    if status:
        row["status"] = status
    agents[agent_id] = row
    save_runtime_state(st)
    return row


def set_runtime_agent_status(agent_id: str, status: str) -> dict[str, Any] | None:
    return touch_runtime_agent(agent_id, status=status)


def sweep_expired_agents(st: dict[str, Any] | None = None, *, persist: bool = True) -> int:
    state = st if st is not None else load_runtime_state()
    agents = ensure_runtime_agents_schema(state)
    now = _now()
    n = 0
    for aid, row in list(agents.items()):
        if not isinstance(row, dict) or row.get("system"):
            continue
        exp = _parse_iso(str(row.get("expires_at") or ""))
        if exp and exp < now and row.get("status") not in ("expired", "suspended"):
            row["status"] = "expired"
            agents[aid] = row
            n += 1
        elif row.get("status") == "active":
            idle_since = _parse_iso(str(row.get("last_activity") or ""))
            if idle_since and (now - idle_since).total_seconds() > _DEFAULT_TTL_SEC * 2:
                row["status"] = "idle"
                agents[aid] = row
    if persist and st is None:
        save_runtime_state(state)
    return n


def _trim_agents(agents: dict[str, Any]) -> None:
    dynamic = [(k, v) for k, v in agents.items() if isinstance(v, dict) and not v.get("system")]
    if len(dynamic) <= _MAX_AGENTS:
        return
    dynamic.sort(key=lambda kv: str((kv[1] or {}).get("last_activity") or ""))
    for k, _ in dynamic[: len(dynamic) - _MAX_AGENTS]:
        agents.pop(k, None)


def office_agent_states() -> list[dict[str, Any]]:
    """Lightweight Office view rows from runtime agents."""
    agents = list_runtime_agents()
    rows: list[dict[str, Any]] = []
    for aid, row in agents.items():
        st = str(row.get("status") or "offline")
        office_state = st
        if st == "active":
            office_state = "busy"
        elif st in ("expired", "suspended"):
            office_state = "offline"
        elif st == "idle":
            office_state = "idle"
        rows.append(
            {
                "agent_id": aid,
                "agent_type": row.get("agent_type"),
                "office_state": office_state,
                "provider": row.get("provider"),
                "model": row.get("model"),
                "created_from_task": row.get("created_from_task"),
                "last_activity": row.get("last_activity"),
                "runtime_managed": row.get("runtime_managed"),
                "system": bool(row.get("system")),
            }
        )
    return rows
