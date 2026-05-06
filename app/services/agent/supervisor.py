"""
Background supervisor for orchestration agents — health checks and CEO interventions.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.services.agent.activity_tracker import get_activity_tracker
from app.services.sub_agent_registry import AgentRegistry, AgentStatus

logger = logging.getLogger(__name__)


class AgentSupervisor:
    """Optional asyncio loop that inspects registry + audit stats."""

    def __init__(self) -> None:
        self.tracker = get_activity_tracker()
        self.registry = AgentRegistry()
        self._monitoring = False
        self._monitor_task: asyncio.Task[None] | None = None

    async def start_monitoring(self) -> None:
        if self._monitor_task is not None and not self._monitor_task.done():
            return
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Agent supervisor monitoring started")

    async def stop_monitoring(self) -> None:
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("Agent supervisor monitoring stopped")

    async def _monitor_loop(self) -> None:
        from app.core.config import get_settings

        while self._monitoring:
            try:
                interval = max(
                    5,
                    int(getattr(get_settings(), "nexa_agent_monitor_interval_seconds", 30) or 30),
                )
                await self._check_agent_health()
                await asyncio.sleep(float(interval))
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("supervisor monitor loop error: %s", exc)
                await asyncio.sleep(10.0)

    async def _check_agent_health(self) -> None:
        agents = self.registry.list_agents(None)
        for agent in agents:
            stats = self.tracker.get_agent_statistics(agent.id, days=1)
            total = int(stats.get("total_actions", 0) or 0)
            rate = float(stats.get("success_rate", 100.0) or 100.0)
            if total > 10 and rate < 70.0:
                await self._alert_agent_issue(
                    agent,
                    f"High failure rate: {rate:.1f}% over last {total} actions (24h)",
                )

            if agent.status == AgentStatus.BUSY:
                la = getattr(agent, "last_active", None)
                if isinstance(la, (int, float)):
                    stuck_duration = time.time() - float(la)
                    if stuck_duration > 300.0:
                        logger.warning(
                            "supervisor: agent %s busy too long (%.0fs); resetting to idle",
                            agent.id,
                            stuck_duration,
                        )
                        self.registry.update_status(agent.id, AgentStatus.IDLE)

    async def _alert_agent_issue(self, agent: Any, issue: str) -> None:
        logger.warning("Agent '%s' (%s) issue: %s", agent.name, agent.id, issue)

    async def intervene(self, agent_id: str, correction: str) -> dict[str, Any]:
        agent = self.registry.get_agent(agent_id)
        if not agent:
            return {"error": "Agent not found"}

        self.tracker.log_action(
            agent_id=agent.id,
            agent_name=agent.name,
            action_type="ceo_intervention",
            input_data={"correction": correction},
            metadata={"intervened_by": "CEO"},
        )
        self.registry.patch_agent(agent.id, status=AgentStatus.PAUSED)
        return {
            "success": True,
            "message": f"Agent '{agent.name}' paused. Guidance recorded: {correction[:500]}",
        }

    async def redirect_agent(self, agent_id: str, new_task: str) -> dict[str, Any]:
        agent = self.registry.get_agent(agent_id)
        if not agent:
            return {"error": "Agent not found"}

        md = dict(agent.metadata or {})
        md["current_task"] = new_task.strip()[:2000]
        self.registry.patch_agent(agent_id, metadata_patch=md)

        self.tracker.log_action(
            agent_id=agent.id,
            agent_name=agent.name,
            action_type="redirected",
            input_data={"new_task": new_task.strip()[:2000]},
            metadata={"redirected_by": "CEO"},
        )
        return {"success": True, "message": f"Agent '{agent.name}' redirected to new task."}

    async def get_agent_insights(self, agent_id: str) -> dict[str, Any]:
        agent = self.registry.get_agent(agent_id)
        if not agent:
            return {"error": "Agent not found"}

        stats = self.tracker.get_agent_statistics(agent.id)
        history = self.tracker.get_agent_history(agent.id, hours=168, limit=50)
        patterns = self._analyze_patterns(history)
        recommendations = self._generate_recommendations(stats, patterns)

        return {
            "agent": {
                "id": agent.id,
                "name": agent.name,
                "domain": agent.domain,
                "status": agent.status.value,
            },
            "statistics": stats,
            "recent_actions": history[:10],
            "patterns": patterns,
            "recommendations": recommendations,
        }

    @staticmethod
    def _analyze_patterns(history: list[dict[str, Any]]) -> dict[str, Any]:
        patterns: dict[str, Any] = {"common_errors": {}, "frequent_actions": {}}
        for action in history:
            if not action.get("success") and action.get("error"):
                err_t = str(action["error"])[:80]
                patterns["common_errors"][err_t] = patterns["common_errors"].get(err_t, 0) + 1
            at = str(action.get("action_type") or "unknown")
            patterns["frequent_actions"][at] = patterns["frequent_actions"].get(at, 0) + 1
        return patterns

    @staticmethod
    def _generate_recommendations(stats: dict[str, Any], patterns: dict[str, Any]) -> list[str]:
        rec: list[str] = []
        if float(stats.get("success_rate", 100.0) or 100.0) < 80.0:
            rec.append(
                "Success rate is below 80%. Narrow scope, add skills, or split tasks."
            )
        cerr = patterns.get("common_errors") or {}
        if cerr:
            top = max(cerr.items(), key=lambda x: x[1])
            rec.append(f"Repeated failures resembling: {top[0][:120]} ({top[1]}×).")
        avg_ms = float(stats.get("avg_duration_ms", 0.0) or 0.0)
        if avg_ms > 10_000.0:
            rec.append("Average action duration exceeds 10s — consider lighter prompts or caching.")
        return rec


_supervisor: AgentSupervisor | None = None


def get_supervisor() -> AgentSupervisor:
    global _supervisor
    if _supervisor is None:
        _supervisor = AgentSupervisor()
    return _supervisor


__all__ = ["AgentSupervisor", "get_supervisor"]
