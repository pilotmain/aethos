# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Bounded workspace ops memory: research chains, deliverable links, continuity (Phase 3 Step 9)."""

from __future__ import annotations

import uuid
from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

_MAX_CHAINS = 64
_MAX_RELATIONSHIPS = 400
_MAX_GOVERNANCE_EVENTS = 120
_MAX_CONTINUITY_SCOPES = 32

_RELATIONSHIP_TYPES = frozenset(
    {
        "derived_from",
        "supersedes",
        "continuation_of",
        "related_to",
        "generated_after",
        "generated_before",
    }
)


def ensure_workspace_ops_schema(st: dict[str, Any]) -> None:
    for key in (
        "research_chains",
        "deliverable_relationships",
        "operator_continuity",
        "workspace_governance_events",
    ):
        if not isinstance(st.get(key), dict):
            st[key] = {}


def create_research_chain(
    *,
    project_id: str | None = None,
    topic: str = "research",
    worker_id: str | None = None,
) -> str:
    st = load_runtime_state()
    ensure_workspace_ops_schema(st)
    cid = f"rch_{uuid.uuid4().hex[:12]}"
    chains = st.setdefault("research_chains", {})
    if isinstance(chains, dict):
        chains[cid] = {
            "research_chain_id": cid,
            "project_id": project_id,
            "topic": (topic or "research")[:120],
            "worker_id": worker_id,
            "related_deliverables": [],
            "comparison_history": [],
            "updated_at": utc_now_iso(),
            "created_at": utc_now_iso(),
        }
        _trim_dict(chains, _MAX_CHAINS)
    save_runtime_state(st)
    return cid


def link_deliverable_to_chain(
    chain_id: str,
    deliverable_id: str,
    *,
    comparison_note: str | None = None,
) -> None:
    st = load_runtime_state()
    ensure_workspace_ops_schema(st)
    chains = st.get("research_chains") or {}
    if not isinstance(chains, dict):
        return
    chain = chains.get(chain_id)
    if not isinstance(chain, dict):
        return
    rel = list(chain.get("related_deliverables") or [])
    if deliverable_id not in rel:
        rel.append(deliverable_id)
    chain["related_deliverables"] = rel[-24:]
    chain["updated_at"] = utc_now_iso()
    if comparison_note:
        hist = list(chain.get("comparison_history") or [])
        hist.append({"at": utc_now_iso(), "note": comparison_note[:500], "deliverable_id": deliverable_id})
        chain["comparison_history"] = hist[-16:]
    chains[chain_id] = chain
    save_runtime_state(st)


def get_research_chain(chain_id: str) -> dict[str, Any] | None:
    st = load_runtime_state()
    chains = st.get("research_chains") or {}
    if isinstance(chains, dict):
        row = chains.get(chain_id)
        return dict(row) if isinstance(row, dict) else None
    return None


def list_research_chains(*, project_id: str | None = None, limit: int = 16) -> list[dict[str, Any]]:
    st = load_runtime_state()
    chains = st.get("research_chains") or {}
    rows: list[dict[str, Any]] = []
    if isinstance(chains, dict):
        for row in chains.values():
            if not isinstance(row, dict):
                continue
            if project_id and str(row.get("project_id") or "") != project_id:
                continue
            rows.append(row)
    rows.sort(key=lambda r: str(r.get("updated_at") or ""), reverse=True)
    return rows[: max(1, min(int(limit), 32))]


def add_deliverable_relationship(
    *,
    from_id: str,
    to_id: str,
    relationship: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    st = load_runtime_state()
    ensure_workspace_ops_schema(st)
    rel_type = relationship if relationship in _RELATIONSHIP_TYPES else "related_to"
    rid = f"rel_{uuid.uuid4().hex[:12]}"
    rels = st.setdefault("deliverable_relationships", {})
    if isinstance(rels, dict):
        rels[rid] = {
            "relationship_id": rid,
            "from_deliverable_id": from_id,
            "to_deliverable_id": to_id,
            "relationship": rel_type,
            "metadata": dict(list((metadata or {}).items())[:8]),
            "created_at": utc_now_iso(),
        }
        _trim_dict(rels, _MAX_RELATIONSHIPS)
    save_runtime_state(st)
    return rid


def relationships_for_deliverable(deliverable_id: str) -> list[dict[str, Any]]:
    st = load_runtime_state()
    rels = st.get("deliverable_relationships") or {}
    out: list[dict[str, Any]] = []
    if isinstance(rels, dict):
        for row in rels.values():
            if not isinstance(row, dict):
                continue
            if row.get("from_deliverable_id") == deliverable_id or row.get("to_deliverable_id") == deliverable_id:
                out.append(row)
    out.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return out[:24]


def set_operator_continuity(chat_key: str, *, scope: dict[str, Any]) -> None:
    st = load_runtime_state()
    ensure_workspace_ops_schema(st)
    cont = st.setdefault("operator_continuity", {})
    if isinstance(cont, dict):
        cont[chat_key] = {**scope, "updated_at": utc_now_iso()}
        _trim_dict(cont, _MAX_CONTINUITY_SCOPES)
    save_runtime_state(st)


def get_operator_continuity(chat_key: str) -> dict[str, Any] | None:
    st = load_runtime_state()
    cont = st.get("operator_continuity") or {}
    if isinstance(cont, dict):
        row = cont.get(chat_key)
        return dict(row) if isinstance(row, dict) else None
    return None


def record_workspace_governance_event(
    event_type: str,
    *,
    who: str = "runtime",
    what: str = "",
    project_id: str | None = None,
    deliverable_id: str | None = None,
    worker_id: str | None = None,
) -> None:
    st = load_runtime_state()
    ensure_workspace_ops_schema(st)
    events = st.setdefault("workspace_governance_events", {})
    if isinstance(events, dict):
        eid = f"wge_{uuid.uuid4().hex[:12]}"
        events[eid] = {
            "event_id": eid,
            "event_type": event_type,
            "who": who,
            "what": (what or event_type)[:500],
            "project_id": project_id,
            "deliverable_id": deliverable_id,
            "worker_id": worker_id,
            "at": utc_now_iso(),
        }
        _trim_dict(events, _MAX_GOVERNANCE_EVENTS)
    save_runtime_state(st)


def list_workspace_governance_events(*, limit: int = 24) -> list[dict[str, Any]]:
    st = load_runtime_state()
    events = st.get("workspace_governance_events") or {}
    rows = [r for r in events.values() if isinstance(r, dict)] if isinstance(events, dict) else []
    rows.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    return rows[: max(1, min(int(limit), 48))]


def _trim_dict(d: dict[str, Any], cap: int) -> None:
    if len(d) <= cap:
        return
    ordered = sorted(d.items(), key=lambda kv: str((kv[1] or {}).get("updated_at") or (kv[1] or {}).get("at") or (kv[1] or {}).get("created_at") or ""))
    for k, _ in ordered[: len(d) - cap]:
        d.pop(k, None)
