# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Dynamic runtime agents — full lifecycle management (Phase 2 Step 8–9)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

ORCHESTRATOR_ID = "aethos_orchestrator"
ORCHESTRATOR_TYPE = "orchestrator"
_DEFAULT_TTL_SEC = 3600
_IDLE_SUSPEND_SEC = 7200
_MAX_AGENTS = 128

LIFECYCLE_STATES = frozenset(
    {"spawned", "active", "busy", "idle", "recovering", "suspended", "expired", "failed"}
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _metrics(st: dict[str, Any]) -> dict[str, Any]:
    m = st.setdefault("runtime_agent_metrics", {})
    if not isinstance(m, dict):
        m = {
            "active_agents": 0,
            "busy_agents": 0,
            "expired_agents": 0,
            "recovered_agents": 0,
            "agent_reassignment_count": 0,
            "agent_runtime_failures": 0,
        }
        st["runtime_agent_metrics"] = m
    for k in (
        "active_agents",
        "busy_agents",
        "expired_agents",
        "recovered_agents",
        "agent_reassignment_count",
        "agent_runtime_failures",
    ):
        m.setdefault(k, 0)
    return m


def agent_runtime_metrics() -> dict[str, Any]:
    st = load_runtime_state()
    _recompute_agent_counts(st)
    return dict(_metrics(st))


def _recompute_agent_counts(st: dict[str, Any]) -> None:
    agents = st.get("runtime_agents") or {}
    m = _metrics(st)
    active = busy = 0
    if isinstance(agents, dict):
        for row in agents.values():
            if not isinstance(row, dict) or row.get("system"):
                continue
            stt = str(row.get("status") or "")
            if stt in ("active", "spawned"):
                active += 1
            elif stt == "busy":
                busy += 1
    m["active_agents"] = active
    m["busy_agents"] = busy


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
            "role": "orchestrator",
            "persistent": True,
            "status": "active",
            "lifecycle": "active",
            "created_from_task": None,
            "provider": "aethos",
            "model": "orchestrator",
            "last_activity": utc_now_iso(),
            "expires_at": None,
            "runtime_managed": True,
            "system": True,
            "assignment": None,
        }
    elif isinstance(orch, dict):
        orch.setdefault("role", "orchestrator")
        orch.setdefault("persistent", True)
    _metrics(st)
    return ra


def recover_runtime_agents_after_restart() -> int:
    """Mark non-system agents recovering then active where still valid."""
    st = load_runtime_state()
    agents = ensure_runtime_agents_schema(st)
    m = _metrics(st)
    n = 0
    for aid, row in list(agents.items()):
        if not isinstance(row, dict) or row.get("system"):
            continue
        if row.get("status") in ("expired", "failed"):
            continue
        row["status"] = "recovering"
        row["lifecycle"] = "recovering"
        agents[aid] = row
        row["status"] = "active"
        row["lifecycle"] = "active"
        row["last_activity"] = utc_now_iso()
        agents[aid] = row
        m["recovered_agents"] = int(m.get("recovered_agents") or 0) + 1
        n += 1
        try:
            from app.services.mission_control.mc_runtime_events import emit_mc_runtime_event

            emit_mc_runtime_event("agent_recovered", agent_id=aid)
        except Exception:
            pass
    if n:
        save_runtime_state(st)
    return n


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
            enriched = dict(row)
            if enriched.get("system"):
                enriched.setdefault("role", "orchestrator")
                enriched.setdefault("persistent", True)
            else:
                enriched.setdefault("role", str(enriched.get("agent_type") or "worker"))
                enriched.setdefault("persistent", False)
            out[str(aid)] = enriched
    return out


def find_active_agent_by_task(agent_type: str, task_key: str) -> dict[str, Any] | None:
    agents = list_runtime_agents(include_expired=False)
    for row in agents.values():
        if not isinstance(row, dict) or row.get("system"):
            continue
        if str(row.get("agent_type") or "") != agent_type:
            continue
        cft = str(row.get("created_from_task") or "")
        assign = row.get("assignment") if isinstance(row.get("assignment"), dict) else {}
        if cft == task_key or str(assign.get("task_id") or "") == task_key:
            if str(row.get("status") or "") in ("active", "busy", "idle", "spawned", "recovering"):
                return row
    return None


def spawn_or_reuse_runtime_agent(
    *,
    agent_type: str,
    created_from_task: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    ttl_sec: int = _DEFAULT_TTL_SEC,
) -> dict[str, Any]:
    """Avoid duplicate agents for the same task key (e.g. repair per project)."""
    key = created_from_task or ""
    existing = find_active_agent_by_task(agent_type, key) if key else None
    if existing:
        touch_runtime_agent(str(existing["agent_id"]), status="busy")
        return existing
    return spawn_runtime_agent(
        agent_type=agent_type,
        created_from_task=created_from_task,
        provider=provider,
        model=model,
        ttl_sec=ttl_sec,
    )


def list_runtime_agents_history(*, limit: int = 24) -> list[dict[str, Any]]:
    agents = list_runtime_agents(include_expired=True)
    rows = [dict(v, agent_id=k) for k, v in agents.items() if isinstance(v, dict)]
    rows.sort(key=lambda r: str(r.get("last_activity") or ""), reverse=True)
    return rows[: max(1, min(int(limit), 64))]


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
        "role": (agent_type or "general").strip().lower(),
        "persistent": False,
        "status": "spawned",
        "lifecycle": "spawned",
        "created_from_task": created_from_task,
        "provider": (provider or "deterministic").strip().lower(),
        "model": (model or "").strip() or None,
        "last_activity": utc_now_iso(),
        "expires_at": expires.isoformat(),
        "runtime_managed": True,
        "system": False,
        "assignment": None,
    }
    row["status"] = "active"
    row["lifecycle"] = "active"
    st = load_runtime_state()
    agents = ensure_runtime_agents_schema(st)
    agents[aid] = row
    _trim_agents(agents)
    _recompute_agent_counts(st)
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


def assign_runtime_agent(agent_id: str, *, task_id: str, workflow_id: str | None = None) -> dict[str, Any] | None:
    st = load_runtime_state()
    agents = ensure_runtime_agents_schema(st)
    row = agents.get(agent_id)
    if not isinstance(row, dict) or row.get("system"):
        return None
    row["status"] = "busy"
    row["lifecycle"] = "busy"
    row["assignment"] = {"task_id": task_id, "workflow_id": workflow_id}
    row["last_activity"] = utc_now_iso()
    agents[agent_id] = row
    m = _metrics(st)
    m["agent_reassignment_count"] = int(m.get("agent_reassignment_count") or 0) + 1
    _recompute_agent_counts(st)
    save_runtime_state(st)
    return row


def release_runtime_agent(agent_id: str) -> dict[str, Any] | None:
    st = load_runtime_state()
    agents = ensure_runtime_agents_schema(st)
    row = agents.get(agent_id)
    if not isinstance(row, dict) or row.get("system"):
        return None
    row["status"] = "idle"
    row["lifecycle"] = "idle"
    row["assignment"] = None
    row["last_activity"] = utc_now_iso()
    agents[agent_id] = row
    _recompute_agent_counts(st)
    save_runtime_state(st)
    return row


def touch_runtime_agent(agent_id: str, *, status: str | None = None) -> dict[str, Any] | None:
    st = load_runtime_state()
    agents = ensure_runtime_agents_schema(st)
    row = agents.get(agent_id)
    if not isinstance(row, dict):
        return None
    row["last_activity"] = utc_now_iso()
    if status and status in LIFECYCLE_STATES:
        row["status"] = status
        row["lifecycle"] = status
    agents[agent_id] = row
    save_runtime_state(st)
    return row


def set_runtime_agent_status(agent_id: str, status: str) -> dict[str, Any] | None:
    return touch_runtime_agent(agent_id, status=status)


def sweep_expired_agents(st: dict[str, Any] | None = None, *, persist: bool = True) -> int:
    state = st if st is not None else load_runtime_state()
    agents = ensure_runtime_agents_schema(state)
    m = _metrics(state)
    now = _now()
    n = 0
    for aid, row in list(agents.items()):
        if not isinstance(row, dict) or row.get("system"):
            continue
        exp = _parse_iso(str(row.get("expires_at") or ""))
        idle_since = _parse_iso(str(row.get("last_activity") or ""))
        stt = str(row.get("status") or "")
        if exp and exp < now and stt not in ("expired", "suspended", "failed"):
            row["status"] = "expired"
            row["lifecycle"] = "expired"
            row["expired_at"] = utc_now_iso()
            agents[aid] = row
            _append_agent_history(state, row)
            m["expired_agents"] = int(m.get("expired_agents") or 0) + 1
            n += 1
            try:
                from app.services.mission_control.mc_runtime_events import emit_mc_runtime_event

                emit_mc_runtime_event("agent_expired", agent_id=aid)
            except Exception:
                pass
        elif stt == "idle" and idle_since and (now - idle_since).total_seconds() > _IDLE_SUSPEND_SEC:
            row["status"] = "suspended"
            row["lifecycle"] = "suspended"
            agents[aid] = row
            try:
                from app.services.mission_control.mc_runtime_events import emit_mc_runtime_event

                emit_mc_runtime_event("agent_suspended", agent_id=aid)
            except Exception:
                pass
        elif stt in ("active", "busy") and idle_since and (now - idle_since).total_seconds() > _DEFAULT_TTL_SEC:
            if stt != "busy":
                row["status"] = "idle"
                row["lifecycle"] = "idle"
                agents[aid] = row
    _recompute_agent_counts(state)
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
    agents = list_runtime_agents()
    rows: list[dict[str, Any]] = []
    for aid, row in agents.items():
        st = str(row.get("lifecycle") or row.get("status") or "offline")
        office_state = st
        if st == "active":
            office_state = "busy" if row.get("assignment") else "active"
        elif st in ("expired", "suspended", "failed"):
            office_state = "offline"
        rows.append(
            {
                "agent_id": aid,
                "agent_type": row.get("agent_type"),
                "office_state": office_state,
                "lifecycle": row.get("lifecycle"),
                "provider": row.get("provider"),
                "model": row.get("model"),
                "created_from_task": row.get("created_from_task"),
                "assignment": row.get("assignment"),
                "last_activity": row.get("last_activity"),
                "runtime_managed": row.get("runtime_managed"),
                "system": bool(row.get("system")),
            }
        )
    return rows


def _append_agent_history(st: dict[str, Any], row: dict[str, Any]) -> None:
    hist = st.setdefault("runtime_agents_history", [])
    if not isinstance(hist, list):
        hist = []
        st["runtime_agents_history"] = hist
    hist.append(
        {
            "agent_id": row.get("agent_id"),
            "agent_type": row.get("agent_type"),
            "status": row.get("status"),
            "expired_at": row.get("expired_at") or utc_now_iso(),
            "created_from_task": row.get("created_from_task"),
        }
    )
    if len(hist) > 200:
        del hist[: len(hist) - 200]


def office_topology(user_id: str | None = None) -> dict[str, Any]:
    from app.services.mission_control.runtime_ownership import build_ownership_chains
    from app.services.mission_control.runtime_event_intelligence import list_normalized_events

    from app.services.mission_control.runtime_event_intelligence import aggregate_events_for_display

    return {
        "agents": office_agent_states(),
        "ownership_chains": build_ownership_chains(user_id),
        "recent_events": aggregate_events_for_display(limit=12),
    }
