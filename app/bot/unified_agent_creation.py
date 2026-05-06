"""Phase 48 — unified agent creation uses :mod:`app.services.sub_agent_natural_creation` (orchestration registry)."""

from __future__ import annotations

from app.services.sub_agent_natural_creation import (
    prefers_registry_sub_agent,
    try_spawn_natural_sub_agents,
)

__all__ = [
    "prefers_registry_sub_agent",
    "try_spawn_natural_sub_agents",
]
