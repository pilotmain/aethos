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
        from app.core.config import get_settings
        from app.services.agent.heartbeat import ORCHESTRATION_HEARTBEAT_EVENT
        from app.services.events.bus import publish

        s = get_settings()
        publish_hb = bool(getattr(s, "nexa_agent_monitoring_enabled", False))

        agents = self.registry.list_agents(None)
        for agent in agents:
            if publish_hb:
                try:
                    publish(
                        {
                            "type": ORCHESTRATION_HEARTBEAT_EVENT,
                            "payload": {
                                "agent_id": agent.id,
                                "domain": agent.domain,
                                "status": agent.status.value,
                                "last_active_ts": getattr(agent, "last_active", None),
                                "parent_chat_id": agent.parent_chat_id,
                            },
                            "agent": agent.name,
                        }
                    )
                except Exception:
                    logger.debug("heartbeat publish skipped", exc_info=True)
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

            # Phase 73 — self-healing pass.
            if bool(getattr(s, "nexa_self_healing_enabled", False)):
                try:
                    self._run_self_healing(agent, stats)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "self_healing pass failed agent=%s: %s", agent.id, exc
                    )

    def _run_self_healing(
        self, agent: Any, stats: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Phase 73 — diagnose -> recover -> escalate when failures exceed the
        configured threshold within the rolling window. Returns the recovery
        result dict (or None when nothing fired) so callers (tests + the
        manual-trigger health API) can introspect the outcome.
        """
        from app.core.config import get_settings
        from app.services.agent.recovery import get_recovery_handler
        from app.services.agent.self_diagnosis import (
            CAUSE_NO_FAILURES,
            get_self_diagnosis,
        )

        s = get_settings()
        threshold = max(
            1, int(getattr(s, "nexa_agent_failure_threshold", 3) or 3)
        )
        window_min = max(
            1, int(getattr(s, "nexa_agent_failure_window_minutes", 60) or 60)
        )
        window_hours = max(1, (window_min // 60) + (1 if window_min % 60 else 0))
        history = self.tracker.get_agent_history(agent.id, hours=window_hours, limit=200)
        recent_fails = sum(1 for h in history if not h.get("success"))
        if recent_fails < threshold:
            return None

        diagnosis = get_self_diagnosis().diagnose(agent)
        if diagnosis.cause_class == CAUSE_NO_FAILURES:
            return None

        # Tracker breadcrumb for the diagnosis itself (separate from the
        # recovery row that the handler writes).
        try:
            self.tracker.log_action(
                agent_id=agent.id,
                agent_name=agent.name,
                action_type="self_heal_diagnosis",
                input_data={"window_minutes": diagnosis.window_minutes},
                output_data={
                    "cause_class": diagnosis.cause_class,
                    "summary": diagnosis.summary,
                    "error_count": diagnosis.error_count,
                    "fingerprint": diagnosis.fingerprint,
                    "used_llm": diagnosis.used_llm,
                },
                success=True,
                metadata={"phase": "73", "self_healing": True},
            )
        except Exception:  # noqa: BLE001
            logger.debug("self_heal_diagnosis tracker log suppressed", exc_info=True)

        handler = get_recovery_handler()
        result = handler.attempt(agent, diagnosis)

        if result.escalate:
            self._escalate_self_heal(agent, diagnosis.to_dict(), result.to_dict())

        return result.to_dict()

    def _escalate_self_heal(
        self,
        agent: Any,
        diagnosis: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        """
        Notify the configured Telegram chat id. Escalation never raises — when
        the chat id is unset (default) we only log + record. The audit row goes
        to the existing agent_audit.db so the CEO dashboard surfaces it.
        """
        from app.core.config import get_settings

        s = get_settings()
        chat_id = (getattr(s, "nexa_agent_escalation_chat_id", "") or "").strip()
        text = (
            f"⚠️ Agent self-heal escalation\n"
            f"agent: {agent.name} ({agent.id})\n"
            f"cause: {diagnosis.get('cause_class')}\n"
            f"strategy: {result.get('strategy')} (succeeded={result.get('succeeded')})\n"
            f"attempts_used: {result.get('attempts_used')}\n"
            f"summary: {diagnosis.get('summary', '')[:600]}"
        )
        try:
            self.tracker.log_action(
                agent_id=agent.id,
                agent_name=agent.name,
                action_type="self_heal_escalation",
                input_data={"diagnosis": diagnosis, "result": result},
                output_data={
                    "telegram_chat_id_set": bool(chat_id),
                    "text_preview": text[:500],
                },
                success=True,
                metadata={"phase": "73", "self_healing": True},
            )
        except Exception:  # noqa: BLE001
            logger.debug("self_heal_escalation tracker log suppressed", exc_info=True)

        if not chat_id:
            logger.warning(
                "Agent '%s' (%s) needs escalation but NEXA_AGENT_ESCALATION_CHAT_ID is unset",
                agent.name,
                agent.id,
            )
            return
        try:
            from app.services.telegram_outbound import send_telegram_message

            send_telegram_message(chat_id, text)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "self_heal_escalation telegram send failed agent=%s: %s",
                agent.id,
                exc,
            )

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
