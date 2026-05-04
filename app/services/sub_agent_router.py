"""
Week 4 Phase 2 — sync routing for orchestration sub-agents (@mentions only).

No execution: Phase 3 will enqueue host/operator work. See docs/AGENT_ORCHESTRATION.md.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.core.config import get_settings
from app.services.gateway.context import GatewayContext
from app.services.sub_agent_registry import AgentRegistry, AgentStatus

logger = logging.getLogger(__name__)


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


class AgentRouter:
    """Routes @mentions to registered sub-agents (sync)."""

    @property
    def registry(self) -> AgentRegistry:
        """Always use the current singleton (tests may :meth:`AgentRegistry.reset`)."""
        return AgentRegistry()

    def route(self, user_input: str, chat_id: str) -> dict[str, Any]:
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

        logger.info(
            "Sub-agent mention routed (no execution in Phase 2)",
            extra={
                "nexa_event": "sub_agent_mention",
                "agent_id": agent.id,
                "agent_name": agent_name,
                "domain": agent.domain,
                "chat_id": chat_id,
            },
        )

        return {
            "handled": True,
            "response": (
                f"Agent '@{agent_name}' (domain: {agent.domain}) is ready.\n\n"
                "(Phase 3 will attach execution for your message.)"
            ),
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
) -> dict[str, Any] | None:
    """
    If orchestration handles this turn, return a gateway payload fragment (``mode`` / ``text`` / ``intent``).
    Otherwise ``None`` so the gateway continues normal routing.
    """
    if not bool(getattr(get_settings(), "nexa_agent_orchestration_enabled", False)):
        return None
    router = AgentRouter()
    chat_key = orchestration_chat_key(gctx)
    out = router.route(user_text, chat_key)
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
    "try_sub_agent_gateway_turn",
]
