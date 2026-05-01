"""
Single routing authority: orchestrator / runtime tools beat implicit web search.

Used to suppress public URL read + web search when the user is clearly in @boss / spawn /
runtime-tool territory so research heuristics do not override orchestration.
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

from app.services.agent_runtime.boss_chat import (
    extract_spawn_group_id_for_chat,
    has_spawn_lifecycle_intent,
)
from app.services.mention_control import parse_mention
from app.services.web_research_intent import web_search_intent_heuristic

logger = logging.getLogger(__name__)


class RouteKind(str, Enum):
    ORCHESTRATOR = "orchestrator"
    RUNTIME_TOOL = "runtime_tool"
    AGENT = "agent"
    OPS = "ops"
    WEB_SEARCH = "web_search"
    FALLBACK = "fallback"


# Bounded spawn / heartbeat wording (subset of boss_chat triggers + tool names).
_RUNTIME_TOOL_PHRASE = re.compile(
    r"(?is)\b("
    r"bounded\s+agent\s+swarm|agent\s+swarm|spawn\s+sessions|spawn\s+with|"
    r"create\s+(?:a\s+)?(?:bounded\s+)?(?:agent\s+)?sessions|create\s+agent\s+sessions|"
    r"create\s+(?:a\s+)?(?:bounded\s+)?(?:agent\s+)?swarm|"
    r"start\s+(?:a\s+)?(?:bounded\s+)?supervised\s+sessions|create\s+a\s+bounded\s+session|"
    r"bounded\s+session|sessions_spawn|background_heartbeat|record\s+heartbeat\b|heartbeat:|update\s+heartbeat"
    r")\b"
)


def build_routing_context(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    mr = parse_mention(t)
    has_spawn_group_id = extract_spawn_group_id_for_chat(t) is not None
    has_boss_mention = bool(re.search(r"(?i)@boss\b", t))
    has_assignment_ids = bool(
        re.search(r"(?is)\bassignment_ids\b", t)
        or re.search(r"(?i)assignment\s*#", t)
        or bool(re.search(r"(?<!\w)#(?:\d{2,})\b", t))
    )
    has_catalog_agent_mention = bool(mr.is_explicit and not mr.error and mr.agent_key)
    contains_runtime_intent = bool(_RUNTIME_TOOL_PHRASE.search(t)) or has_spawn_lifecycle_intent(t)
    is_explicit_web_request = bool(web_search_intent_heuristic(t))
    has_ops_intent = bool(
        re.search(
            r"(?is)(?:^|[\s])(?:/ops\b|/deploy\b|nexa\s+ops\b|\bops\s+status\b|\bops\s+health\b)",
            t,
        )
    )

    return {
        "has_boss_mention": has_boss_mention,
        "has_spawn_group_id": has_spawn_group_id,
        "has_assignment_ids": has_assignment_ids,
        "has_agent_mention": has_catalog_agent_mention,
        "is_explicit_web_request": is_explicit_web_request,
        "contains_runtime_intent": contains_runtime_intent,
        "has_ops_intent": has_ops_intent,
    }


def resolve_route(context: dict[str, Any]) -> RouteKind:
    if context.get("has_spawn_group_id"):
        return RouteKind.ORCHESTRATOR
    if context.get("has_boss_mention"):
        return RouteKind.ORCHESTRATOR
    if context.get("contains_runtime_intent"):
        return RouteKind.RUNTIME_TOOL
    if context.get("has_agent_mention"):
        return RouteKind.AGENT
    if context.get("has_ops_intent"):
        return RouteKind.OPS
    if context.get("is_explicit_web_request"):
        return RouteKind.WEB_SEARCH
    return RouteKind.FALLBACK


_ROUTE_REASONS: dict[RouteKind, str] = {
    RouteKind.ORCHESTRATOR: "spawn lifecycle, @boss, or orchestration signals",
    RouteKind.RUNTIME_TOOL: "sessions_spawn / heartbeat / bounded swarm wording",
    RouteKind.AGENT: "explicit @mention to a catalog agent",
    RouteKind.OPS: "explicit ops / deploy intent",
    RouteKind.WEB_SEARCH: "explicit web search phrasing",
    RouteKind.FALLBACK: "no deterministic route matched",
}


def resolve_route_dict(
    text: str,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Public routing decision with stable keys for logs and tests.

    ``user_id`` / ``session_id`` are accepted for API parity with the plan doc; reserved for future use.
    """
    _ = user_id, session_id
    ctx = build_routing_context(text)
    kind = resolve_route(ctx)
    conf = 1.0 if kind in (RouteKind.ORCHESTRATOR, RouteKind.RUNTIME_TOOL) else 0.85
    return {
        "route": kind.value,
        "reason": _ROUTE_REASONS.get(kind, ""),
        "confidence": conf,
        "context": ctx,
    }


def log_routing_decision(kind: RouteKind, context: dict[str, Any], text_preview: str) -> None:
    preview = (text_preview or "").strip().replace("\n", " ")[:160]
    logger.info(
        "routing_authority kind=%s ctx=%s preview=%r",
        kind.value,
        {k: context[k] for k in sorted(context.keys())},
        preview,
    )


def should_suppress_public_web_pipeline(text: str) -> bool:
    """
    True when public URL read + web search tool paths should not run (orchestrator / runtime tools).
    """
    ctx = build_routing_context(text)
    kind = resolve_route(ctx)
    log_routing_decision(kind, ctx, text)
    return kind in (RouteKind.ORCHESTRATOR, RouteKind.RUNTIME_TOOL)
