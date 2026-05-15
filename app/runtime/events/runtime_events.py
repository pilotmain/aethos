# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime event emission (persistent buffer + log + in-process bus)."""

from __future__ import annotations

import uuid
from typing import Any

from app.orchestration import orchestration_log
from app.runtime.runtime_state import utc_now_iso


_MAX_BUFFER = 2500


def emit_runtime_event(st: dict[str, Any], event: str, **fields: Any) -> dict[str, Any]:
    """
    Record a structured runtime event (task/workflow/session lifecycle).

    - Appends to ``st["runtime_event_buffer"]`` (caller persists).
    - Writes JSON line to ``~/.aethos/logs/runtime_events.log``.
    - Publishes to :mod:`app.services.events.bus` for WebSocket/SSE consumers.
    """
    eid = str(uuid.uuid4())
    ts = utc_now_iso()
    row: dict[str, Any] = {
        "event_id": eid,
        "timestamp": ts,
        "event": str(event),
        **fields,
    }
    buf = st.setdefault("runtime_event_buffer", [])
    if not isinstance(buf, list):
        st["runtime_event_buffer"] = []
        buf = st["runtime_event_buffer"]
    buf.append(row)
    if len(buf) > _MAX_BUFFER:
        del buf[: len(buf) - _MAX_BUFFER]

    orchestration_log.append_json_log("runtime_events", str(event), event_id=eid, timestamp=ts, **fields)

    try:
        from app.services.events.bus import publish

        publish(
            {
                "type": f"runtime.{event}",
                "task_id": fields.get("task_id"),
                "agent": fields.get("assigned_agent_id") or fields.get("agent_id"),
                "mission_id": fields.get("plan_id"),
                "payload": row,
            }
        )
    except Exception:
        pass
    return row
