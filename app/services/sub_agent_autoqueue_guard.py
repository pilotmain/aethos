"""
Restrict in-process autoqueue (``execute_payload``) for sub-agents (Week 5).

When checks fail, callers should fall back to the normal job queue (if DB + user available).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from app.core.config import get_settings
from app.services.sub_agent_registry import SubAgent

logger = logging.getLogger(__name__)

_autoqueue_success_counts: dict[str, int] = defaultdict(int)


def reset_autoqueue_counts_for_tests() -> None:
    _autoqueue_success_counts.clear()


def should_run_autoqueue_payload(
    chat_id: str,
    domain: str,
    agent: SubAgent,
) -> tuple[bool, str | None, bool]:
    """
    Decide whether to run ``execute_payload`` in-process.

    Returns:
        (allow_execute, user_message_if_denied, prefer_queue_fallback)
    """
    s = get_settings()
    if not bool(getattr(s, "nexa_agent_orchestration_autoqueue", False)):
        return True, None, False

    raw_chats = (getattr(s, "nexa_agent_autoqueue_allowlist_chats", None) or "").strip()
    allowed_chats = [c.strip() for c in raw_chats.split(",") if c.strip()]
    if allowed_chats and chat_id not in allowed_chats:
        logger.warning(
            "autoqueue blocked: chat not allowlisted",
            extra={
                "nexa_event": "autoqueue_blocked",
                "reason": "chat_not_allowlisted",
                "chat_id": chat_id,
                "agent_id": agent.id,
            },
        )
        return (
            False,
            "In-process auto-queue is restricted for this chat. Using approval queue instead.",
            True,
        )

    raw_domains = (getattr(s, "nexa_agent_autoqueue_allowlist_domains", None) or "").strip()
    allowed_domains = [d.strip().lower() for d in raw_domains.split(",") if d.strip()]
    dom = (domain or "").strip().lower()
    if allowed_domains and dom not in allowed_domains:
        logger.warning(
            "autoqueue blocked: domain not allowlisted",
            extra={
                "nexa_event": "autoqueue_blocked",
                "reason": "domain_not_allowlisted",
                "domain": domain,
                "agent_id": agent.id,
            },
        )
        return (
            False,
            f"In-process auto-queue is not allowlisted for domain {domain!r}. Using approval queue instead.",
            True,
        )

    threshold = int(getattr(s, "nexa_agent_autoqueue_require_approval_after", 0) or 0)
    if threshold > 0:
        cnt = _autoqueue_success_counts.get(agent.id, 0)
        if cnt >= threshold:
            logger.info(
                "autoqueue threshold: forcing queue",
                extra={
                    "nexa_event": "autoqueue_threshold",
                    "agent_id": agent.id,
                    "call_count": cnt,
                    "threshold": threshold,
                },
            )
            return (
                False,
                f"Auto-queue cap reached ({cnt}/{threshold}) for this sub-agent. Using approval queue for this run.",
                True,
            )

    return True, None, False


def record_autoqueue_success(agent_id: str) -> None:
    _autoqueue_success_counts[agent_id] = _autoqueue_success_counts.get(agent_id, 0) + 1


__all__ = [
    "should_run_autoqueue_payload",
    "record_autoqueue_success",
    "reset_autoqueue_counts_for_tests",
]
