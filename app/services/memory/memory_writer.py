# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Write mission summaries into the persistent memory layer (post-mission)."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings
from app.services.logging.logger import get_logger
from app.services.memory.memory_store import MemoryStore

_log = get_logger("memory_writer")


def _trim(s: str, n: int) -> str:
    t = (s or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def summary_from_mission(
    mission: dict[str, Any],
    agents: list[dict[str, Any]],
    *,
    mission_id: str,
    timed_out: bool,
) -> tuple[str, str, str, dict[str, Any]]:
    title = str(mission.get("title") or "Mission")
    status = "timeout" if timed_out else "completed"
    lines = [f"## Mission `{mission_id}`", f"**{title}** — _{status}_", ""]
    meta: dict[str, Any] = {
        "mission_id": mission_id,
        "status": status,
        "agent_count": len(agents),
    }
    for a in agents:
        h = str(a.get("handle") or "")
        out = a.get("output")
        if isinstance(out, dict):
            otype = str(out.get("type") or "result")
            snippet = _trim(json.dumps(out, default=str, sort_keys=True), 400)
        else:
            otype = "result"
            snippet = _trim(str(out), 400)
        lines.append(f"- **{h}** ({otype}): {snippet}")
    body = "\n".join(lines)
    return "mission_summary", f"Mission: {title[:200]}", body, meta


class MemoryWriter:
    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or MemoryStore()

    def write_mission_memory(
        self,
        user_id: str,
        mission_id: str,
        mission: dict[str, Any],
        agents: list[dict[str, Any]],
        *,
        timed_out: bool = False,
    ) -> dict[str, Any] | None:
        s = get_settings()
        if not getattr(s, "nexa_memory_layer_enabled", True):
            return None
        try:
            kind, title, body, meta = summary_from_mission(
                mission, agents, mission_id=mission_id, timed_out=timed_out
            )
            rec = self.store.append_entry(
                user_id, kind=kind, title=title, body_md=body, meta=meta
            )
            _log.info("memory.mission_saved user_id=%s mission_id=%s entry=%s", user_id, mission_id, rec.get("id"))
            try:
                from app.services.memory.intelligence import maybe_post_mission_memory_pass

                maybe_post_mission_memory_pass(user_id, store=self.store)
            except Exception:
                _log.debug("memory.post_mission_pass skipped", exc_info=True)
            return rec
        except OSError as exc:
            _log.warning("memory.write_failed %s", exc)
            return None


__all__ = ["MemoryWriter", "summary_from_mission"]
