"""Linear execution chains across tasks (persistent)."""

from __future__ import annotations

import uuid
from typing import Any

from app.execution import execution_plan


def chains(st: dict[str, Any]) -> dict[str, Any]:
    root = execution_plan.execution_root(st)
    c = root.setdefault("chains", {})
    if not isinstance(c, dict):
        root["chains"] = {}
        return root["chains"]
    return c


def create_chain(st: dict[str, Any], task_ids: list[str]) -> str:
    cid = str(uuid.uuid4())
    chains(st)[cid] = {
        "chain_id": cid,
        "task_ids": [str(x) for x in task_ids],
        "cursor": 0,
        "status": "active",
    }
    return cid


def get_chain(st: dict[str, Any], chain_id: str) -> dict[str, Any] | None:
    c = chains(st).get(chain_id)
    return c if isinstance(c, dict) else None


def advance_chain_cursor(st: dict[str, Any], chain_id: str) -> None:
    ch = get_chain(st, chain_id)
    if not ch:
        return
    cur = int(ch.get("cursor") or 0) + 1
    ch["cursor"] = cur
    ids = ch.get("task_ids") or []
    if cur >= len(ids):
        ch["status"] = "completed"
