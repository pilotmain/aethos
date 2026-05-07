"""Unified agent creation (barrel).

Implementation lives in :mod:`app.services.sub_agent_natural_creation` (Phase 48/49 NL parsing +
registry spawn). Import from here for backwards-compatible imports.
"""

from __future__ import annotations

from app.services.sub_agent_natural_creation import (
    looks_like_registry_agent_creation_nl,
    prefers_registry_sub_agent,
    try_spawn_natural_sub_agents,
)

__all__ = [
    "looks_like_registry_agent_creation_nl",
    "prefers_registry_sub_agent",
    "try_spawn_natural_sub_agents",
]
