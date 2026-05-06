"""Orchestration heartbeat — emitted on the runtime event bus when supervisor monitoring is enabled."""

from __future__ import annotations

ORCHESTRATION_HEARTBEAT_EVENT = "orchestration.agent_heartbeat"

__all__ = ["ORCHESTRATION_HEARTBEAT_EVENT"]
