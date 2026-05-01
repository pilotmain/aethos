from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentDefinition
from app.services.agent_registry import DEFAULT_AGENTS


def sync_agent_definitions(db: Session) -> int:
    """Create missing `agent_definitions` rows from DEFAULT_AGENTS. Returns rows inserted."""
    n = 0
    for key, meta in DEFAULT_AGENTS.items():
        st = select(AgentDefinition).where(AgentDefinition.key == key)
        if db.scalars(st).first():
            continue
        spec = {**meta}
        tools = spec.pop("allowed_tools", None)
        db.add(
            AgentDefinition(
                key=key,
                display_name=str(spec.get("display_name", key)),
                description=str(spec.get("description", "")),
                system_prompt="",
                allowed_tools=list(tools) if tools is not None else [],
                is_enabled=True,
            )
        )
        n += 1
    if n:
        db.commit()
    return n
