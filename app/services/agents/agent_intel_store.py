# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 46C — lightweight persistence for per-handle agent performance (JSON beside memory index)."""

from __future__ import annotations

import json
from typing import Any

from app.services.memory.memory_store import MemoryStore


def _path(user_id: str) -> Any:
    return MemoryStore().user_dir(user_id) / "agent_intel.json"


def record_agent_outcome(
    user_id: str,
    agent_handle: str,
    *,
    success: bool,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Increment runs / successes and maintain a simple performance score."""
    uid = (user_id or "").strip()
    h = (agent_handle or "").strip()[:128]
    if not uid or not h:
        return {"ok": False, "error": "missing_user_or_handle"}
    p = _path(uid)
    data: dict[str, Any] = {}
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    slot = data.setdefault(
        h,
        {"runs": 0, "successes": 0, "performance_score": 0.5, "memory": []},
    )
    slot["runs"] = int(slot.get("runs") or 0) + 1
    if success:
        slot["successes"] = int(slot.get("successes") or 0) + 1
    runs = max(1, int(slot["runs"]))
    slot["performance_score"] = round(float(slot["successes"]) / runs, 4)
    mem = slot.setdefault("memory", [])
    if isinstance(mem, list) and meta:
        mem.append({"success": success, "meta": dict(meta or {})})
        slot["memory"] = mem[-40:]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "handle": h, "performance_score": slot["performance_score"]}


def list_agent_intel_profiles(user_id: str, *, limit: int = 30) -> list[dict[str, Any]]:
    """Mission Control slice — one row per agent handle."""
    uid = (user_id or "").strip()
    if not uid:
        return []
    p = _path(uid)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out: list[dict[str, Any]] = []
    for handle, blob in list(data.items())[:limit]:
        if not isinstance(blob, dict):
            continue
        out.append(
            {
                "handle": handle,
                "runs": int(blob.get("runs") or 0),
                "successes": int(blob.get("successes") or 0),
                "performance_score": float(blob.get("performance_score") or 0),
            }
        )
    return sorted(out, key=lambda x: x.get("performance_score") or 0, reverse=True)


__all__ = ["list_agent_intel_profiles", "record_agent_outcome"]
