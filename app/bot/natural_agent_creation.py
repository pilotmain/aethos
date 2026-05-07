"""
Natural-language agent creation for channels that want a single import path.

Imperative phrases (e.g. "create five agents: …") spawn **orchestration sub-agents**
(Mission Control / ``/subagent list``), not LLM custom-agent profiles. Implementation
is in :mod:`app.services.sub_agent_natural_creation`.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.sub_agent_natural_creation import (
    looks_like_registry_agent_creation_nl,
    prefers_registry_sub_agent,
    try_spawn_natural_sub_agents,
)

__all__ = [
    "looks_like_registry_agent_creation_nl",
    "prefers_registry_sub_agent",
    "spawn_sub_agents_from_natural_language",
    "try_spawn_natural_sub_agents",
]


def spawn_sub_agents_from_natural_language(
    db: Session | None,
    app_user_id: str,
    user_text: str,
    *,
    parent_chat_id: str,
) -> str | None:
    """Create registry sub-agents from user text; returns a user-visible message or ``None``."""
    return try_spawn_natural_sub_agents(
        db, app_user_id, user_text, parent_chat_id=parent_chat_id
    )
