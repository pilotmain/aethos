# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Trusted chat/domain/agent auto-approval for host payloads (Week 5.5).

Skips the Jobs approval queue when :mod:`app.core.config` flags allow and criteria match.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from app.core.config import get_settings

if TYPE_CHECKING:
    from app.services.sub_agent_registry import SubAgent

logger = logging.getLogger(__name__)


def should_auto_approve(
    chat_id: str,
    domain: str,
    *,
    agent: Optional["SubAgent"] = None,
    action: str | None = None,
) -> tuple[bool, str]:
    """
    Returns (allow_auto_execute, reason_code).

    Empty ``nexa_auto_approve_chats`` → any chat passes the chat filter.
    Empty ``nexa_auto_approve_domains`` → any domain passes the domain filter.
    A ``SubAgent`` with ``trusted=True`` passes regardless of chat/domain lists (still respects global enable + log_only).
    """
    del action  # reserved for future policy
    s = get_settings()
    if not bool(getattr(s, "nexa_auto_approve_enabled", False)):
        return False, "auto_approve_disabled"

    if bool(getattr(s, "nexa_auto_approve_log_only", False)):
        logger.info(
            "auto_approve dry run — would evaluate chat=%s domain=%s agent_trusted=%s",
            chat_id,
            domain,
            getattr(agent, "trusted", False) if agent else False,
            extra={"nexa_event": "auto_approve_dry_run", "chat_id": chat_id, "domain": domain},
        )
        return False, "log_only_mode"

    if agent is not None and bool(getattr(agent, "trusted", False)):
        logger.info(
            "auto_approve: trusted agent",
            extra={
                "nexa_event": "auto_approve_triggered",
                "reason": "trusted_agent",
                "chat_id": chat_id,
                "domain": domain,
                "agent_id": agent.id,
            },
        )
        return True, "trusted_agent"

    raw_chats = (getattr(s, "nexa_auto_approve_chats", None) or "").strip()
    allowed_chats = [c.strip() for c in raw_chats.split(",") if c.strip()]
    if allowed_chats and chat_id not in allowed_chats:
        logger.info(
            "auto_approve skipped: chat not allowlisted",
            extra={
                "nexa_event": "auto_approve_skipped",
                "reason": "chat_not_allowlisted",
                "chat_id": chat_id,
            },
        )
        return False, "chat_not_allowlisted"

    dom = (domain or "").strip().lower()
    raw_domains = (getattr(s, "nexa_auto_approve_domains", None) or "").strip()
    allowed_domains = [d.strip().lower() for d in raw_domains.split(",") if d.strip()]
    if allowed_domains and dom not in allowed_domains:
        logger.info(
            "auto_approve skipped: domain not allowlisted",
            extra={
                "nexa_event": "auto_approve_skipped",
                "reason": "domain_not_allowlisted",
                "domain": domain,
                "chat_id": chat_id,
            },
        )
        return False, "domain_not_allowlisted"

    logger.info(
        "auto_approve triggered",
        extra={
            "nexa_event": "auto_approve_triggered",
            "reason": "allowlists_ok",
            "chat_id": chat_id,
            "domain": domain,
        },
    )
    return True, "auto_approved"


def get_skip_message() -> str:
    return "📋 Queued for approval (auto-approve is not enabled for this chat/domain)."


def get_auto_approve_message(domain: str, steps: int) -> str:
    d = (domain or "operation").strip()
    return f"✅ Auto-approved: **{d}** ({steps} step{'s' if steps != 1 else ''}) — executing now…"


__all__ = [
    "should_auto_approve",
    "get_skip_message",
    "get_auto_approve_message",
]
