# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Week 4 — sub-agent routing (Phase 2) and execution dispatch (Phase 3).

Leading ``@mentions`` → registry lookup → :class:`AgentExecutor` (Phase 66 adds optional
natural-language phrases when the named agent exists in this chat's registry).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.gateway.context import GatewayContext
from app.services.sub_agent_registry import AgentRegistry, AgentStatus, SubAgent

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


def resolve_agent_for_dispatch(
    registry: AgentRegistry,
    name: str,
    chat_id: str,
    user_id: str | None,
) -> SubAgent | None:
    """Resolve a sub-agent for this chat, then fall back to any agent visible to ``user_id``."""

    ag = registry.resolve_agent_by_name(name, chat_id)
    if ag is not None:
        return ag
    uid = (user_id or "").strip()
    if not uid:
        return None
    global_agent = registry.get_agent_by_name_for_app_user(name, uid)
    if global_agent is None and uid:
        nm = (name or "").strip().lower()
        if nm and not nm.endswith("_agent"):
            global_agent = registry.get_agent_by_name_for_app_user(f"{nm}_agent", uid)
        if global_agent is None and nm.endswith("_agent"):
            global_agent = registry.get_agent_by_name_for_app_user(nm[: -len("_agent")], uid)
    if global_agent:
        # Auto-link to current chat for future mentions
        registry.patch_agent(global_agent.id, parent_chat_id=chat_id)
        logger.info(f"Auto-linked global agent {name} to chat {chat_id}")
        return global_agent
    return None


def try_extract_natural_language_sub_agent(
    text: str,
    chat_id: str,
    registry: AgentRegistry,
    *,
    user_id: str | None = None,
) -> tuple[SubAgent, str] | None:
    """
    If ``text`` names a **registered** sub-agent in ``chat_id`` via common NL patterns, return
    ``(agent, instruction)``. Otherwise ``None`` so the gateway can fall through to Mission Control / chat.

    Intentionally conservative: unknown names never match (no hijack of normal conversation).
    """
    raw = (text or "").strip()
    if not raw or raw.startswith("/"):
        return None

    def _resolve(nm: str) -> SubAgent | None:
        return resolve_agent_for_dispatch(registry, nm, chat_id, user_id)

    m = re.match(r"^\s*what\s+is\s+([a-zA-Z0-9_-]+)\s+doing\b", raw, re.I)
    if m:
        ag = _resolve(m.group(1))
        if ag is not None:
            return (ag, "status")

    m = re.match(r"^\s*(?:ask|tell)\s+([a-zA-Z0-9_-]+)\s+to\s+(.+)$", raw, re.I | re.DOTALL)
    if m:
        ag = _resolve(m.group(1))
        if ag is not None:
            cmd = (m.group(2) or "").strip()
            if cmd:
                return (ag, cmd)

    m = re.match(r"^\s*get\s+([a-zA-Z0-9_-]+)\s+to\s+(.+)$", raw, re.I | re.DOTALL)
    if m:
        ag = _resolve(m.group(1))
        if ag is not None:
            cmd = (m.group(2) or "").strip()
            if cmd:
                return (ag, cmd)

    m = re.match(r"^\s*have\s+([a-zA-Z0-9_-]+)\s+(.+)$", raw, re.I | re.DOTALL)
    if m:
        ag = _resolve(m.group(1))
        if ag is not None:
            cmd = (m.group(2) or "").strip()
            if cmd:
                return (ag, cmd)

    m = re.match(r"^\s*make\s+([a-zA-Z0-9_-]+)\s+(.+)$", raw, re.I | re.DOTALL)
    if m:
        ag = _resolve(m.group(1))
        if ag is not None:
            cmd = (m.group(2) or "").strip()
            if cmd:
                return (ag, cmd)

    agents = sorted(registry.list_agents(chat_id), key=lambda a: len(a.name or ""), reverse=True)
    for ag in agents:
        name = (ag.name or "").strip()
        if not name:
            continue
        if re.match(rf"^\s*{re.escape(name)}\s*$", raw, re.I):
            return (ag, "status")
        m2 = re.match(rf"^\s*{re.escape(name)}\s+(.+)$", raw, re.I | re.DOTALL)
        if m2:
            cmd = (m2.group(1) or "").strip()
            if cmd:
                return (ag, cmd)
    return None


def _maybe_auto_recover_terminated_for_dispatch(
    agent: SubAgent,
    registry: AgentRegistry,
) -> SubAgent:
    """
    When enabled, move TERMINATED orchestration agents back to IDLE so assignments can run.

    Idle cleanup marks agents TERMINATED without deleting them; operators asked for seamless
    reassignment without manual CEO Recover when ``nexa_assignment_auto_recover`` is true.
    """
    if agent.status != AgentStatus.TERMINATED:
        return agent
    s = get_settings()
    if not bool(getattr(s, "nexa_assignment_auto_recover", False)):
        return agent
    wait_s = float(getattr(s, "nexa_assignment_auto_recover_wait_seconds", 0.0) or 0.0)
    registry.patch_agent(
        agent.id,
        status=AgentStatus.IDLE,
        metadata_patch={
            "auto_recovered_at": time.time(),
            "auto_recovered_via": "sub_agent_assignment_dispatch",
        },
    )
    try:
        from app.services.agent.activity_tracker import get_activity_tracker

        get_activity_tracker().log_action(
            agent_id=agent.id,
            agent_name=agent.name,
            action_type="assignment_auto_recover",
            input_data={"from_status": "terminated"},
            output_data={"to_status": "idle"},
            success=True,
            metadata={"via": "sub_agent_router"},
        )
    except Exception:  # noqa: BLE001
        logger.debug("assignment_auto_recover tracker log suppressed", exc_info=True)

    if wait_s > 0:
        time.sleep(min(wait_s, 60.0))

    refreshed = registry.get_agent(agent.id)
    logger.info(
        "assignment auto-recovery: revived terminated agent %s → idle",
        agent.name,
        extra={"nexa_event": "assignment_auto_recover", "agent_id": agent.id},
    )
    return refreshed or agent


class AgentRouter:
    """Routes ``@mentions`` and (Phase 66) NL phrases to registered sub-agents (sync)."""

    @property
    def registry(self) -> AgentRegistry:
        """Always use the current singleton (tests may :meth:`AgentRegistry.reset`)."""
        return AgentRegistry()

    def _dispatch_known_sub_agent(
        self,
        agent: SubAgent,
        *,
        display_name: str,
        clean_message: str,
        chat_id: str,
        db: Session | None,
        user_id: str | None,
        web_session_id: str,
        natural_language: bool = False,
    ) -> dict[str, Any]:
        agent_name = (display_name or agent.name or "").strip() or agent.name

        agent = _maybe_auto_recover_terminated_for_dispatch(agent, self.registry)

        if agent.status != AgentStatus.IDLE:
            hint = (
                "Say `resume` to restart it, or wait until it finishes."
                if agent.status == AgentStatus.PAUSED
                else "It's busy right now — try again in a moment."
            )
            return {
                "handled": True,
                "response": (f"⏳ Agent **@{agent_name}** is currently {agent.status.value}. {hint}"),
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
                        f"✅ **@{agent_name}** ({agent.domain}) is ready.\n\n"
                        f"💡 Tell it what to do: \"@{agent_name} <your request>\""
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
                "natural_language": natural_language,
            },
        )

        return {
            "handled": True,
            "response": exec_out,
            "agent_id": agent.id,
            "agent_name": agent_name,
            "clean_message": clean_message,
        }

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

        from app.services.agent_runtime_truth import try_route_agent_status_query

        status_q = try_route_agent_status_query(
            user_input, chat_id, user_id=user_id, db=db
        )
        if status_q and status_q.get("handled"):
            return status_q

        mention = self._parse_mention(user_input)
        if mention is not None:
            agent_name, clean_message = mention
            agent = resolve_agent_for_dispatch(
                self.registry,
                agent_name,
                chat_id,
                user_id,
            )
            if agent is None:
                return {
                    "handled": True,
                    "response": (
                        f"Agent **@{agent_name}** was not found in this chat.\n\n"
                        "**Options:**\n"
                        f"1. Create it: `create a {agent_name} agent`\n"
                        "2. List existing agents: `/subagent list`\n"
                        "3. Use built-in flows: **Development**, **QA Agent**, etc."
                    ),
                    "agent_id": None,
                    "agent_name": agent_name,
                    "clean_message": clean_message,
                }
            return self._dispatch_known_sub_agent(
                agent,
                display_name=agent_name,
                clean_message=clean_message,
                chat_id=chat_id,
                db=db,
                user_id=user_id,
                web_session_id=web_session_id,
                natural_language=False,
            )

        if bool(getattr(get_settings(), "nexa_natural_agent_invocation", True)):
            nl = try_extract_natural_language_sub_agent(
                user_input, chat_id, self.registry, user_id=user_id
            )
            if nl is not None:
                agent, instruction = nl
                return self._dispatch_known_sub_agent(
                    agent,
                    display_name=agent.name,
                    clean_message=instruction,
                    chat_id=chat_id,
                    db=db,
                    user_id=user_id,
                    web_session_id=web_session_id,
                    natural_language=True,
                )

        return {"handled": False}

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
    "resolve_agent_for_dispatch",
    "telegram_agent_registry_chat_id",
    "try_extract_natural_language_sub_agent",
    "try_sub_agent_gateway_turn",
]
