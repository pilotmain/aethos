# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Natural-language agent-to-agent task chaining (registry sub-agents)."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.services.gateway.context import GatewayContext
from app.services.sub_agent_executor import AgentExecutor
from app.services.sub_agent_registry import AgentRegistry, AgentStatus, SubAgent


def parse_inter_agent_steps(text: str) -> list[tuple[str, str]] | None:
    """
    Parse multi-step agent instructions.

    Supported:
    - ``ask marketing_agent to … and ask qa_agent to …`` / ``…, then ask …``
    - ``ask marketing_agent to …. Then ask qa_agent to …`` (sentence + **Then**)
    - ``ask marketing_agent to …. ask qa_agent to …`` (two sentences, no **then**)
    - ``ask marketing_agent to …`` / ``tell marketing_agent to …``

    Steps are executed as conversational handoffs; QA ``review`` tasks do not require file paths
    (see :meth:`~app.services.sub_agent_executor.AgentExecutor._qa_or_test`).
    """
    raw = (text or "").strip()
    if not raw:
        return None
    line = raw.splitlines()[0].strip()

    m_then = re.search(
        r"(?is)^ask\s+@?([\w-]+)\s+to\s+(.+?)\s*,\s*then\s+(?:ask|tell)\s+@?([\w-]+)\s+to\s+(.+?)(?:[.?!]+)?\s*$",
        line,
    )
    if m_then:
        a1, t1, a2, t2 = m_then.group(1), m_then.group(2).strip(), m_then.group(3), m_then.group(4).strip()
        if a1 and t1 and a2 and t2:
            return [(a1, t1), (a2, t2)]

    m_then_amp = re.search(
        r"(?is)^ask\s+@?([\w-]+)\s+to\s+(.+?)\s*&\s*(?:ask|tell)\s+@?([\w-]+)\s+to\s+(.+?)(?:[.?!]+)?\s*$",
        line,
    )
    if m_then_amp:
        a1, t1, a2, t2 = (
            m_then_amp.group(1),
            m_then_amp.group(2).strip(),
            m_then_amp.group(3),
            m_then_amp.group(4).strip(),
        )
        if a1 and t1 and a2 and t2:
            return [(a1, t1), (a2, t2)]

    m_then_dot = re.search(
        r"(?is)^ask\s+@?([\w-]+)\s+to\s+(.+?)\s*\.\s+then\s+(?:ask|tell)\s+@?([\w-]+)\s+to\s+(.+?)(?:[.?!]+)?\s*$",
        line,
    )
    if m_then_dot:
        a1, t1, a2, t2 = (
            m_then_dot.group(1),
            m_then_dot.group(2).strip(),
            m_then_dot.group(3),
            m_then_dot.group(4).strip(),
        )
        if a1 and t1 and a2 and t2:
            return [(a1, t1), (a2, t2)]

    # "Ask A to B. Then ask C to D" / "Ask A to B. Ask C to D" (sentence boundary; common in chat)
    m_sentence_chain = re.search(
        r"(?is)^ask\s+@?([\w-]+)\s+to\s+(.+?)\.\s+(?:then\s+)?(?:ask|tell)\s+@?([\w-]+)\s+to\s+(.+?)(?:[.?!]+)?\s*$",
        line,
    )
    if m_sentence_chain:
        a1, t1, a2, t2 = (
            m_sentence_chain.group(1),
            m_sentence_chain.group(2).strip(),
            m_sentence_chain.group(3),
            m_sentence_chain.group(4).strip(),
        )
        if a1 and t1 and a2 and t2:
            return [(a1, t1), (a2, t2)]

    m_then2 = re.search(
        r"(?is)^ask\s+@?([\w-]+)\s+to\s+(.+?)\s+then\s+(?:ask|tell)\s+@?([\w-]+)\s+to\s+(.+?)(?:[.?!]+)?\s*$",
        line,
    )
    if m_then2:
        a1, t1, a2, t2 = m_then2.group(1), m_then2.group(2).strip(), m_then2.group(3), m_then2.group(4).strip()
        if a1 and t1 and a2 and t2:
            return [(a1, t1), (a2, t2)]

    m_and_then = re.search(
        r"(?is)^ask\s+@?([\w-]+)\s+to\s+(.+?)\s+and\s+then\s+(?:ask|tell)\s+@?([\w-]+)\s+to\s+(.+?)(?:[.?!]+)?\s*$",
        line,
    )
    if m_and_then:
        a1, t1, a2, t2 = (
            m_and_then.group(1),
            m_and_then.group(2).strip(),
            m_and_then.group(3),
            m_and_then.group(4).strip(),
        )
        if a1 and t1 and a2 and t2:
            return [(a1, t1), (a2, t2)]

    m = re.search(
        r"(?is)^ask\s+@?([\w-]+)\s+to\s+(.+?)\s+and\s+(?:ask|tell)\s+@?([\w-]+)\s+to\s+(.+?)(?:[.?!]+)?\s*$",
        line,
    )
    if m:
        a1, t1, a2, t2 = m.group(1), m.group(2).strip(), m.group(3), m.group(4).strip()
        if a1 and t1 and a2 and t2:
            return [(a1, t1), (a2, t2)]

    m2 = re.search(r"(?is)^(?:ask|tell)\s+@?([\w-]+)\s+to\s+(.+?)(?:[.?!]+)?\s*$", line)
    if m2:
        a, t = m2.group(1), m2.group(2).strip()
        if a and t:
            return [(a, t)]

    return None


def _resolve_agent(registry: AgentRegistry, name: str, chat_id: str, user_id: str):
    ag = registry.resolve_agent_by_name(name, chat_id)
    if ag is not None:
        return ag
    ag = registry.get_agent_by_name_for_app_user(name, user_id)
    if ag is not None:
        registry.patch_agent(ag.id, parent_chat_id=chat_id)
    return ag


def run_inter_agent_steps(
    db: Session | None,
    *,
    user_id: str,
    chat_id: str,
    web_session_id: str,
    steps: list[tuple[str, str]],
) -> str:
    """Execute each (agent_name, task) sequentially via :class:`~app.services.sub_agent_executor.AgentExecutor`."""
    registry = AgentRegistry()
    executor = AgentExecutor()
    uid = (user_id or "").strip()
    wid = (web_session_id or "default").strip()[:64] or "default"
    chunks: list[str] = []
    prior_snippets: list[str] = []

    for agent_name, task in steps:
        ag = _resolve_agent(registry, agent_name, chat_id, uid)
        if ag is None:
            chunks.append(
                f"❌ **@{agent_name}** was not found in this chat. "
                f"Create it first (e.g. “create a {agent_name.replace('_', ' ')} agent”)."
            )
            continue
        effective_task = (task or "").strip()
        if prior_snippets:
            handoff = "\n\n---\n**Handoff (prior agent output):**\n" + prior_snippets[-1][
                :4000
            ]
            effective_task = (effective_task + handoff).strip()[:24_000]
        try:
            out = executor.execute(
                ag,
                effective_task,
                chat_id,
                db=db,
                user_id=uid,
                web_session_id=wid,
            )
        except Exception as exc:  # noqa: BLE001
            chunks.append(f"### @{agent_name}\n\n⚠️ {exc!s}")
            continue
        chunks.append(f"### @{agent_name}\n\n{out}")
        prior_snippets.append(f"@{agent_name}: {(out or '')[:6000]}")

    return "\n\n---\n\n".join(chunks).strip()[:24_000]


class AgentNegotiator:
    """Score registered sub-agents for a task string (keyword overlap with capabilities/domain)."""

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self._registry = registry or AgentRegistry()

    def _score_agent(self, agent: SubAgent, task: str) -> tuple[float, float]:
        tl = (task or "").lower()
        blob = " ".join(agent.capabilities).lower() + " " + (agent.domain or "").lower()
        hits = sum(1 for w in tl.replace(",", " ").split() if len(w) > 2 and w in blob)
        confidence = min(1.0, 0.25 + hits * 0.18)
        est = max(8.0, 120.0 - hits * 15.0)
        return confidence, est

    def negotiate_task(self, task: str, *, user_id: str, chat_id: str | None = None) -> dict[str, Any]:
        uid = (user_id or "").strip()
        if not uid:
            return {"error": "missing user_id"}
        agents = (
            self._registry.list_agents(chat_id)
            if chat_id
            else self._registry.list_agents_for_app_user(uid)
        )
        active = [a for a in agents if a.status != AgentStatus.TERMINATED]
        bids: list[dict[str, Any]] = []
        for ag in active:
            conf, est = self._score_agent(ag, task)
            if conf >= 0.25:
                bids.append(
                    {
                        "agent": ag.name,
                        "confidence": round(conf, 3),
                        "estimated_time_seconds": round(est, 1),
                        "domain": ag.domain,
                    }
                )
        if not bids:
            return {"error": "No agent can handle this task", "candidates": []}
        best = max(bids, key=lambda x: x["confidence"])
        return {"selected_agent": best["agent"], "bid": best, "candidates": bids}

    def delegate_subtasks_plan(self, sub_tasks: list[str], *, user_id: str, chat_id: str | None = None) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for st in sub_tasks:
            sel = self.negotiate_task(st, user_id=user_id, chat_id=chat_id)
            results.append({"task": st, "selection": sel})
        return {"delegated": len(results), "results": results}


def try_inter_agent_gateway_turn(
    gctx: GatewayContext,
    text: str,
    db: Session | None,
) -> dict[str, Any] | None:
    """Gateway hook: NL agent-to-agent orchestration."""
    uid = (gctx.user_id or "").strip()
    if not uid:
        tid = str(gctx.extras.get("telegram_user_id") or "").strip()
        if tid:
            uid = f"tg_{tid}"
    if not uid:
        sid = str(
            gctx.extras.get("web_session_id") or gctx.extras.get("conversation_id") or ""
        ).strip()[:80]
        if sid:
            uid = f"session:{sid}"
    if not uid:
        return None
    steps = parse_inter_agent_steps(text)
    if not steps:
        return None
    from app.services.sub_agent_router import orchestration_chat_key

    chat_id = orchestration_chat_key(gctx)
    wid = str(gctx.extras.get("web_session_id") or "default").strip()[:64] or "default"
    body = run_inter_agent_steps(
        db,
        user_id=uid,
        chat_id=chat_id,
        web_session_id=wid,
        steps=steps,
    )
    return {
        "mode": "chat",
        "text": body,
        "intent": "inter_agent_chain",
        "inter_agent": True,
    }


__all__ = [
    "AgentNegotiator",
    "parse_inter_agent_steps",
    "run_inter_agent_steps",
    "try_inter_agent_gateway_turn",
]
