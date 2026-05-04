"""Structured audit lines for sub-agent orchestration (Week 5)."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def log_agent_event(
    event_type: str,
    *,
    agent_id: str | None = None,
    agent_name: str | None = None,
    domain: str | None = None,
    chat_id: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
    success: bool | None = None,
    error: str | None = None,
    duration_ms: float | None = None,
    autoqueue: bool | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit one INFO line with ``nexa_event=agent_audit`` and consistent extra fields."""
    payload: dict[str, Any] = {
        "nexa_event": "agent_audit",
        "agent_audit_event": event_type,
        "agent_audit_ts": time.time(),
    }
    if agent_id is not None:
        payload["agent_id"] = agent_id
    if agent_name is not None:
        payload["agent_name"] = agent_name
    if domain is not None:
        payload["domain"] = domain
    if chat_id is not None:
        payload["chat_id"] = chat_id
    if user_id is not None:
        payload["user_id"] = (user_id or "")[:128]
    if action is not None:
        payload["action"] = action[:2000]
    if success is not None:
        payload["success"] = success
    if error is not None:
        payload["error"] = error[:2000]
    if duration_ms is not None:
        payload["duration_ms"] = round(duration_ms, 3)
    if autoqueue is not None:
        payload["autoqueue"] = autoqueue
    if extra:
        for k, v in extra.items():
            if k not in payload:
                payload[k] = v
    logger.info("agent_audit %s", event_type, extra=payload)


__all__ = ["log_agent_event"]
