# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Persistent coordination agent rows in ``coordination_agents``."""

from __future__ import annotations

from typing import Any


def agents_map(st: dict[str, Any]) -> dict[str, Any]:
    m = st.setdefault("coordination_agents", {})
    if not isinstance(m, dict):
        st["coordination_agents"] = {}
        return st["coordination_agents"]
    return m


def get_agent(st: dict[str, Any], agent_id: str) -> dict[str, Any] | None:
    row = agents_map(st).get(str(agent_id))
    return row if isinstance(row, dict) else None


def upsert_agent(st: dict[str, Any], agent_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    aid = str(agent_id)
    cur = dict(agents_map(st).get(aid) or {})
    cur.update(patch)
    agents_map(st)[aid] = cur
    return cur


def list_agents_for_user(st: dict[str, Any], user_id: str) -> list[dict[str, Any]]:
    uid = str(user_id or "").strip()
    out: list[dict[str, Any]] = []
    for _aid, row in agents_map(st).items():
        if not isinstance(row, dict):
            continue
        if uid and str(row.get("user_id") or "") != uid:
            continue
        out.append(dict(row))
    out.sort(key=lambda r: str(r.get("last_heartbeat") or r.get("created_at") or ""), reverse=True)
    return out
