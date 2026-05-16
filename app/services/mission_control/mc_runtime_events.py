# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control runtime event helpers (Phase 2 Step 8)."""

from __future__ import annotations

from typing import Any

from app.runtime.events.runtime_events import emit_runtime_event
from app.runtime.runtime_state import load_runtime_state, save_runtime_state

_MC_EVENT_TYPES = frozenset(
    {
        "task_created",
        "task_started",
        "task_completed",
        "task_failed",
        "deployment_started",
        "deployment_completed",
        "deployment_failed",
        "deployment_rollback_started",
        "agent_spawned",
        "agent_suspended",
        "agent_expired",
        "agent_recovered",
        "brain_selected",
        "provider_selected",
        "repair_started",
        "repair_verified",
        "repair_redeploy_started",
        "runtime_recovered",
        "queue_pressure",
        "retry_pressure",
        "privacy_redaction",
    }
)


def emit_mc_runtime_event(event_type: str, **fields: Any) -> dict[str, Any]:
    """Persist + bus-publish a Mission Control runtime event."""
    et = (event_type or "").strip()
    if et not in _MC_EVENT_TYPES:
        et = et or "runtime_event"
    st = load_runtime_state()
    row = emit_runtime_event(st, et, mc_event_type=et, **fields)
    save_runtime_state(st)
    try:
        from app.services.events.bus import publish

        publish(
            {
                "type": f"mission_control.{et}",
                "payload": row,
                "user_id": fields.get("user_id"),
                "project_id": fields.get("project_id"),
            }
        )
    except Exception:
        pass
    return row


def recent_mc_runtime_events(*, limit: int = 80) -> list[dict[str, Any]]:
    st = load_runtime_state()
    buf = st.get("runtime_event_buffer") or []
    if not isinstance(buf, list):
        return []
    lim = max(1, min(int(limit), 500))
    return list(buf[-lim:])
