"""
Week 4 — sub-agent routing (Phase 2) and execution dispatch (Phase 3).

@mentions (leading) → registry lookup → optional :class:`AgentExecutor` for non-empty text.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.gateway.context import GatewayContext
from app.services.sub_agent_registry import AgentRegistry, AgentStatus

logger = logging.getLogger(__name__)

_last_orch_cleanup_mono: float = 0.0


def _maybe_cleanup_idle_agents() -> None:
    """Run registry idle cleanup at most every ``nexa_agent_cleanup_interval_seconds``."""
    global _last_orch_cleanup_mono
    s = get_settings()
    interval = max(30.0, float(getattr(s, "nexa_agent_cleanup_interval_seconds", 300)))
    now = time.monotonic()
    if now - _last_orch_cleanup_mono < interval:
        return
    _last_orch_cleanup_mono = now
    n = AgentRegistry().cleanup_idle_agents()
    if n:
        logger.info(
            "orchestration idle cleanup: terminated %s agent(s)",
            n,
            extra={"nexa_event": "sub_agent_idle_cleanup", "terminated": n},
        )


def orchestration_chat_key(gctx: GatewayContext) -> str:
    """
    Stable scope for SubAgent.parent_chat_id across channels.

    Telegram prefers real chat id when present; web uses user + session id.
    """
    channel = (gctx.channel or "web").strip().lower()
    uid = (gctx.user_id or "").strip()[:128]
    if channel == "telegram":
        tid = str(gctx.extras.get("telegram_chat_id") or "").strip()
        if tid:
            return f"telegram:{tid}"
        return f"telegram:user:{uid}"
    sid = str(
        gctx.extras.get("web_session_id") or gctx.extras.get("conversation_id") or "default"
    ).strip()[:64]
    return f"web:{uid}:{sid}"


def orchestration_web_session_id(gctx: GatewayContext) -> str:
    return str(
        gctx.extras.get("web_session_id") or gctx.extras.get("conversation_id") or "default"
    ).strip()[:64] or "default"


def telegram_agent_registry_chat_id(telegram_chat_id: int | str | None) -> str:
    """
    Canonical ``parent_chat_id`` for Telegram ↔ :class:`~app.services.sub_agent_registry.AgentRegistry`.

    Matches :func:`orchestration_chat_key` when ``telegram_chat_id`` is present in gateway extras.
    """
    tid = str(telegram_chat_id or "").strip()
    return f"telegram:{tid}" if tid else "telegram:unknown"


class AgentRouter:
    """Routes @mentions to registered sub-agents (sync)."""

    @property
    def registry(self) -> AgentRegistry:
        """Always use the current singleton (tests may :meth:`AgentRegistry.reset`)."""
        return AgentRegistry()

    def route(
        self,
        user_input: str,
        chat_id: str,
        *,
        db: Session | None = None,
        user_id: str | None = None,
        web_session_id: str = "default",
    ) -> dict[str, Any]:
        """
        Returns a dict with at least ``handled: bool``.
        When handled and routed, includes ``response``, ``agent_id``, ``agent_name``, ``clean_message``.
        """
        if not bool(getattr(get_settings(), "nexa_agent_orchestration_enabled", False)):
            return {"handled": False}

        mention = self._parse_mention(user_input)
        if mention is None:
            return {"handled": False}

        agent_name, clean_message = mention
        agent = self.registry.get_agent_by_name(agent_name, chat_id)
        if agent is None:
            return {
                "handled": True,
                "response": (
                    f"Sub-agent '@{agent_name}' was not found for this chat. "
                    "Create a sub-agent for this session first (same chat scope as routing)."
                ),
                "agent_id": None,
                "agent_name": agent_name,
                "clean_message": clean_message,
            }

        if agent.status != AgentStatus.IDLE:
            return {
                "handled": True,
                "response": (
                    f"Agent '@{agent_name}' is {agent.status.value}. Try again when it is idle."
                ),
                "agent_id": agent.id,
                "agent_name": agent_name,
                "clean_message": clean_message,
            }

        effective_message = (clean_message or "").strip()
        if not effective_message:
            name_l = (agent_name or "").strip().lower()
            dom_l = (agent.domain or "").strip().lower()
            if name_l in ("qa_agent", "qa", "security_agent") or dom_l in ("qa", "security", "sec"):
                effective_message = (
                    "security review: scan the default workspace root for heuristic secrets and unsafe patterns."
                )
            elif bool(getattr(get_settings(), "nexa_sub_agent_auto_execute", True)):
                effective_message = "status"
            else:
                return {
                    "handled": True,
                    "response": (
                        f"Agent '@{agent_name}' ({agent.domain}) is ready. "
                        f"Send `@{agent_name} <instruction>` to run tools."
                    ),
                    "agent_id": agent.id,
                    "agent_name": agent_name,
                    "clean_message": clean_message,
                }

        from app.services.sub_agent_executor import AgentExecutor

        exec_out = AgentExecutor().execute(
            agent,
            effective_message,
            chat_id,
            db=db,
            user_id=(user_id or "").strip(),
            web_session_id=web_session_id,
        )

        logger.info(
            "Sub-agent executed message",
            extra={
                "nexa_event": "sub_agent_executed",
                "agent_id": agent.id,
                "agent_name": agent_name,
                "domain": agent.domain,
                "chat_id": chat_id,
            },
        )

        return {
            "handled": True,
            "response": exec_out,
            "agent_id": agent.id,
            "agent_name": agent_name,
            "clean_message": clean_message,
        }

    def _parse_mention(self, text: str) -> tuple[str, str] | None:
        """Leading ``@name`` only (Phase 2). Optional remainder is ``clean_message``."""
        t = (text or "").strip()
        if not t:
            return None
        m = re.match(r"^@([a-zA-Z0-9_-]+)\s*(.*)$", t, re.DOTALL)
        if not m:
            return None
        return (m.group(1), (m.group(2) or "").strip())


def try_sub_agent_gateway_turn(
    gctx: GatewayContext,
    user_text: str,
    db: Session | None = None,
) -> dict[str, Any] | None:
    """
    If orchestration handles this turn, return a gateway payload fragment (``mode`` / ``text`` / ``intent``).
    Otherwise ``None`` so the gateway continues normal routing.
    """
    if not bool(getattr(get_settings(), "nexa_agent_orchestration_enabled", False)):
        return None
    _maybe_cleanup_idle_agents()
    router = AgentRouter()
    chat_key = orchestration_chat_key(gctx)
    wid = orchestration_web_session_id(gctx)
    out = router.route(
        user_text,
        chat_key,
        db=db,
        user_id=(gctx.user_id or "").strip() or None,
        web_session_id=wid,
    )
    if not out.get("handled"):
        return None
    text_out = out.get("response")
    if text_out is None:
        return None
    return {
        "mode": "chat",
        "text": text_out,
        "intent": "sub_agent_orchestration",
        "sub_agent_id": out.get("agent_id"),
        "sub_agent_name": out.get("agent_name"),
    }


__all__ = [
    "AgentRouter",
    "orchestration_chat_key",
    "orchestration_web_session_id",
    "telegram_agent_registry_chat_id",
    "try_sub_agent_gateway_turn",
]
