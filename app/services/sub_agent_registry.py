"""
In-memory **orchestration** sub-agent registry (Week 4 Phase 1).

Distinct from :mod:`app.services.agent_registry` (platform `DEFAULT_AGENTS` catalog).

Suitable for single-worker API processes. For multi-replica / HA, use a
persistent backend (DB/Redis) — see docs/AGENT_ORCHESTRATION.md.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.config import get_settings
from app.services.sub_agent_audit import log_agent_event

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Lifecycle status of a sub-agent handle."""

    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    TERMINATED = "terminated"


@dataclass
class SubAgent:
    """Logical sub-agent record (not a separate OS process)."""

    id: str
    name: str
    domain: str
    capabilities: list[str]
    parent_chat_id: str
    trusted: bool = False
    status: AgentStatus = AgentStatus.IDLE
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.last_active = time.time()


def _default_capabilities_for_domain(domain: str) -> list[str]:
    domain_capabilities: dict[str, list[str]] = {
        "git": ["status", "clone", "commit", "push", "pull"],
        "vercel": ["list", "deploy", "remove", "logs"],
        "railway": ["up", "down", "logs", "status"],
        "test": ["pytest", "unit", "integration", "lint"],
    }
    return list(domain_capabilities.get(domain, []))


class AgentRegistry:
    """
    Process-wide registry (singleton). For tests, call :meth:`reset`.
    """

    _instance: AgentRegistry | None = None

    def __new__(cls) -> AgentRegistry:
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._agents: dict[str, SubAgent] = {}
            cls._instance = inst
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Clear singleton state (testing only)."""
        cls._instance = None

    def spawn_agent(
        self,
        name: str,
        domain: str,
        chat_id: str,
        capabilities: list[str] | None = None,
        *,
        trusted: bool = False,
    ) -> SubAgent | None:
        settings = get_settings()
        if not bool(getattr(settings, "nexa_agent_orchestration_enabled", False)):
            logger.warning("agent orchestration disabled; spawn ignored")
            return None

        max_c = max(1, int(getattr(settings, "nexa_agent_max_per_chat", 5)))
        chat_agents = self.list_agents(chat_id)
        if len(chat_agents) >= max_c:
            logger.warning(
                "chat %s at max agents (%s)",
                chat_id,
                max_c,
            )
            return None

        for a in chat_agents:
            if a.name == name:
                logger.warning("duplicate agent name %r in chat %s", name, chat_id)
                return None

        caps = list(capabilities) if capabilities is not None else _default_capabilities_for_domain(domain)
        agent_id = str(uuid.uuid4())[:8]
        agent = SubAgent(
            id=agent_id,
            name=name,
            domain=domain,
            capabilities=caps,
            parent_chat_id=chat_id,
            trusted=bool(trusted),
        )
        self._agents[agent_id] = agent
        logger.info(
            "Spawned agent %s (%s) domain=%s chat=%s",
            name,
            agent_id,
            domain,
            chat_id,
            extra={
                "nexa_event": "sub_agent_spawned",
                "agent_id": agent_id,
                "agent_name": name,
                "domain": domain,
                "chat_id": chat_id,
                "capabilities": caps,
            },
        )
        log_agent_event(
            "spawn",
            agent_id=agent_id,
            agent_name=name,
            domain=domain,
            chat_id=chat_id,
            success=True,
        )
        return agent

    def get_agent(self, agent_id: str) -> SubAgent | None:
        return self._agents.get(agent_id)

    def get_agent_by_name(self, name: str, chat_id: str) -> SubAgent | None:
        for a in self.list_agents(chat_id):
            if a.name == name:
                return a
        return None

    def list_agents(self, chat_id: str | None = None) -> list[SubAgent]:
        agents = list(self._agents.values())
        if chat_id is not None:
            agents = [a for a in agents if a.parent_chat_id == chat_id]
        return agents

    def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        agent.status = status
        if status == AgentStatus.IDLE:
            agent.touch()
        logger.debug("agent %s status -> %s", agent_id, status.value)
        return True

    def touch_agent(self, agent_id: str) -> bool:
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        agent.touch()
        return True

    def terminate_agent(self, agent_id: str) -> bool:
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        agent.status = AgentStatus.TERMINATED
        logger.info("Terminated agent %s (%s)", agent_id, agent.name)
        log_agent_event(
            "terminate",
            agent_id=agent_id,
            agent_name=agent.name,
            domain=agent.domain,
            chat_id=agent.parent_chat_id,
            success=True,
        )
        return True

    def cleanup_idle_agents(self) -> int:
        settings = get_settings()
        now = time.time()
        timeout_seconds = max(1, int(getattr(settings, "nexa_agent_idle_timeout_seconds", 3600)))
        terminated = 0
        for agent_id, ag in list(self._agents.items()):
            if ag.status == AgentStatus.IDLE and (now - ag.last_active) > timeout_seconds:
                if self.terminate_agent(agent_id):
                    terminated += 1
        if terminated:
            logger.info("Cleanup: terminated %s idle agent(s)", terminated)
        return terminated

    def get_stats(self, chat_id: str | None = None) -> dict[str, Any]:
        agents = self.list_agents(chat_id) if chat_id is not None else list(self._agents.values())
        status_counts: dict[str, int] = {s.value: 0 for s in AgentStatus}
        for a in agents:
            status_counts[a.status.value] = status_counts.get(a.status.value, 0) + 1
        domains = list({a.domain for a in agents})
        return {
            "total_agents": len(agents),
            "status_counts": status_counts,
            "domains": domains,
        }


__all__ = ["AgentRegistry", "AgentStatus", "SubAgent"]
