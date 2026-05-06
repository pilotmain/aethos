"""
Orchestration sub-agent registry (Week 4 Phase 1).

Distinct from :mod:`app.services.agent_registry` (platform `DEFAULT_AGENTS` catalog).

Loads/saves rows to ``aethos_orchestration_sub_agents`` so agents survive API restarts.
Persistence is skipped while ``pytest`` is imported so unit tests stay in-memory only.
Multi-replica APIs still need a shared store or sticky routing — see docs/AGENT_ORCHESTRATION.md.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy import delete as sql_delete
from sqlalchemy import select

from app.core.config import get_settings
from app.services.sub_agent_audit import log_agent_event

logger = logging.getLogger(__name__)


def _orch_registry_db_enabled() -> bool:
    """Avoid SQLite / DB writes during pytest (unit tests expect pure in-memory state)."""
    return "pytest" not in sys.modules


class AgentStatus(Enum):
    """Lifecycle status of a sub-agent handle."""

    IDLE = "idle"
    BUSY = "busy"
    PAUSED = "paused"
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
        "ops": ["railway", "status", "projects", "deploy", "logs"],
        "backend": ["api", "services", "deploy"],
        "frontend": ["ui", "react", "next"],
        "qa": ["pytest", "lint", "integration", "review"],
        "test": ["pytest", "unit", "integration", "lint"],
        "marketing": ["campaign", "copy", "brand", "brief"],
        "security": ["scan", "review", "audit"],
    }
    return list(domain_capabilities.get(domain, []))


def _row_to_subagent(row: Any) -> SubAgent:
    try:
        st = AgentStatus(row.status)
    except Exception:
        st = AgentStatus.IDLE
    return SubAgent(
        id=row.id,
        name=row.name,
        domain=row.domain,
        capabilities=list(row.capabilities or []),
        parent_chat_id=row.parent_chat_id,
        trusted=bool(row.trusted),
        status=st,
        created_at=float(row.created_at),
        last_active=float(row.last_active),
        metadata=dict(row.agent_metadata or {}),
    )


class AgentRegistry:
    """
    Process-wide registry (singleton). For tests, call :meth:`reset`.
    """

    _instance: AgentRegistry | None = None

    def __new__(cls) -> AgentRegistry:
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._agents: dict[str, SubAgent] = {}
            inst._orch_hydrated = False
            cls._instance = inst
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Clear singleton state (testing only)."""
        cls._instance = None

    def _ensure_loaded(self) -> None:
        if self._orch_hydrated:
            return
        self._orch_hydrated = True
        if not _orch_registry_db_enabled():
            return
        try:
            from app.core.db import SessionLocal
            from app.models.aethos_orchestration_sub_agent import AethosOrchestrationSubAgent

            with SessionLocal() as db:
                rows = db.execute(select(AethosOrchestrationSubAgent)).scalars().all()
                for row in rows:
                    try:
                        self._agents[row.id] = _row_to_subagent(row)
                    except Exception as exc:
                        logger.warning("skip bad orchestration agent row id=%s: %s", row.id, exc)
        except Exception as exc:
            logger.warning("orchestration registry DB load failed (continuing in-memory): %s", exc)

    def _persist_agent(self, agent: SubAgent) -> None:
        if not _orch_registry_db_enabled():
            return
        try:
            from app.core.db import SessionLocal
            from app.models.aethos_orchestration_sub_agent import AethosOrchestrationSubAgent

            with SessionLocal() as db:
                row = db.get(AethosOrchestrationSubAgent, agent.id)
                if row is None:
                    row = AethosOrchestrationSubAgent(id=agent.id)
                    db.add(row)
                row.name = agent.name
                row.domain = agent.domain
                row.parent_chat_id = agent.parent_chat_id
                row.capabilities = list(agent.capabilities or [])
                row.trusted = bool(agent.trusted)
                row.status = agent.status.value
                row.created_at = float(agent.created_at)
                row.last_active = float(agent.last_active)
                row.agent_metadata = dict(agent.metadata or {})
                db.commit()
        except Exception as exc:
            logger.warning("orchestration agent persist failed id=%s: %s", agent.id, exc)

    def _delete_persisted(self, agent_id: str) -> None:
        if not _orch_registry_db_enabled():
            return
        try:
            from app.core.db import SessionLocal
            from app.models.aethos_orchestration_sub_agent import AethosOrchestrationSubAgent

            with SessionLocal() as db:
                db.execute(sql_delete(AethosOrchestrationSubAgent).where(AethosOrchestrationSubAgent.id == agent_id))
                db.commit()
        except Exception as exc:
            logger.warning("orchestration agent delete failed id=%s: %s", agent_id, exc)

    def spawn_agent(
        self,
        name: str,
        domain: str,
        chat_id: str,
        capabilities: list[str] | None = None,
        *,
        trusted: bool = False,
    ) -> SubAgent | None:
        self._ensure_loaded()
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
        self._persist_agent(agent)
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
        self._ensure_loaded()
        return self._agents.get(agent_id)

    def get_agent_by_name(self, name: str, chat_id: str) -> SubAgent | None:
        for a in self.list_agents(chat_id):
            if a.name == name:
                return a
        return None

    def list_agents(self, chat_id: str | None = None) -> list[SubAgent]:
        self._ensure_loaded()
        agents = list(self._agents.values())
        if chat_id is not None:
            agents = [a for a in agents if a.parent_chat_id == chat_id]
        return agents

    def list_agents_merged(self, scopes: list[str]) -> list[SubAgent]:
        """Return unique agents across ``parent_chat_id`` values (first occurrence wins)."""
        seen: set[str] = set()
        out: list[SubAgent] = []
        for scope in scopes:
            for a in self.list_agents(scope):
                if a.id not in seen:
                    seen.add(a.id)
                    out.append(a)
        return out

    def get_agent_by_name_in_scopes(self, name: str, scopes: list[str]) -> SubAgent | None:
        for scope in scopes:
            a = self.get_agent_by_name(name, scope)
            if a:
                return a
        return None

    def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        self._ensure_loaded()
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        agent.status = status
        if status == AgentStatus.IDLE:
            agent.touch()
        logger.debug("agent %s status -> %s", agent_id, status.value)
        self._persist_agent(agent)
        return True

    def touch_agent(self, agent_id: str) -> bool:
        self._ensure_loaded()
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        agent.touch()
        self._persist_agent(agent)
        return True

    def terminate_agent(self, agent_id: str) -> bool:
        self._ensure_loaded()
        agent = self._agents.get(agent_id)
        if not agent:
            return False
        agent.status = AgentStatus.TERMINATED
        self._persist_agent(agent)
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

    def remove_agent(self, agent_id: str) -> bool:
        """Permanently drop an agent from this process (hard delete)."""
        self._ensure_loaded()
        agent = self._agents.pop(agent_id, None)
        if agent is None:
            return False
        self._delete_persisted(agent_id)
        logger.info("Removed agent %s (%s) chat=%s", agent_id, agent.name, agent.parent_chat_id)
        log_agent_event(
            "remove",
            agent_id=agent_id,
            agent_name=agent.name,
            domain=agent.domain,
            chat_id=agent.parent_chat_id,
            success=True,
        )
        return True

    def patch_agent(
        self,
        agent_id: str,
        *,
        name: str | None = None,
        domain: str | None = None,
        capabilities: list[str] | None = None,
        status: AgentStatus | None = None,
        trusted: bool | None = None,
        metadata_patch: dict[str, Any] | None = None,
    ) -> SubAgent | None:
        self._ensure_loaded()
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        if name is not None:
            agent.name = name.strip()[:120]
        if domain is not None:
            agent.domain = domain.strip().lower()[:64]
        if capabilities is not None:
            agent.capabilities = list(capabilities)
        if status is not None:
            agent.status = status
        if trusted is not None:
            agent.trusted = bool(trusted)
        if metadata_patch:
            md = dict(agent.metadata or {})
            md.update(metadata_patch)
            agent.metadata = md
        agent.touch()
        self._persist_agent(agent)
        return agent

    def cleanup_idle_agents(self) -> int:
        self._ensure_loaded()
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
        self._ensure_loaded()
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
