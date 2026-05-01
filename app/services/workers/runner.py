"""Agent execution — provider gateway (privacy firewall inside) + artifact handoff."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.artifacts.store import read_artifacts, write_artifact
from app.services.events.bus import publish
from app.services.providers.gateway import call_provider
from app.services.providers.types import ProviderRequest
from app.services.tools.registry import get_provider_for_tool, select_tool_for_agent


def run_agent(agent: dict[str, Any], db: Session) -> dict[str, Any]:
    tool_name = select_tool_for_agent(agent)
    provider_name = get_provider_for_tool(tool_name)

    mission_id = agent.get("mission_id")
    previous_outputs = read_artifacts(db, mission_id)

    request = ProviderRequest(
        user_id=str(agent.get("user_id") or "dev_user"),
        mission_id=mission_id,
        agent_handle=agent["handle"],
        provider=provider_name,
        model=None,
        purpose=tool_name,
        payload={
            "task": agent["task"],
            "agent": agent["role"],
            "handle": agent["handle"],
            "tool": tool_name,
            "inputs": previous_outputs,
        },
        db=db,
    )

    response = call_provider(request)

    if response.blocked:
        return {"type": "blocked", "error": response.error}

    output = response.output if response.output is not None else {"type": "empty"}
    write_artifact(db, mission_id, agent["handle"], output)
    publish(
        {
            "type": "artifact.created",
            "mission_id": mission_id,
            "agent": agent["handle"],
            "artifact": output,
        }
    )
    return output


__all__ = ["run_agent"]
