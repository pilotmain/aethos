# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Shared helpers for Phase 28 budget checks and LLM usage recording.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.services.budget.helpers import budget_enabled
from app.services.budget.models import UsageType
from app.services.budget.tracker import BudgetTracker
from app.services.llm.base import Message

logger = logging.getLogger(__name__)

_BLOCKED_REPLY = (
    "⚠️ Budget limit reached for this team member (work hours). "
    "Ask an admin to raise the monthly limit or wait for the next reset."
)


def estimate_tokens_from_text(text: str | None) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_tokens_from_messages(messages: list[Message]) -> int:
    total = 0
    for m in messages:
        c = m.content
        if isinstance(c, str):
            total += len(c)
        elif isinstance(c, list):
            total += sum(len(str(p)) for p in c)
        else:
            total += len(str(c))
    return max(1, total // 4)


def llm_preflight_estimate(messages: list[Message], max_tokens: int | None) -> int:
    """Input estimate plus assumed completion budget for pre-call gate."""
    inp = estimate_tokens_from_messages(messages)
    mt = int(max_tokens or get_settings().nexa_llm_max_tokens or 4096)
    return inp + max(512, min(mt, 32_000))


def check_budget_before_llm(member_id: str, estimated_tokens: int) -> tuple[bool, str | None]:
    if not budget_enabled() or not member_id:
        return True, None
    tracker = BudgetTracker()
    tracker.check_and_reset_budget(member_id)
    budget = tracker.get_or_create_budget(member_id)
    if budget.can_execute(estimated_tokens):
        return True, None
    logger.warning(
        "budget block member=%s est=%s used=%s limit=%s",
        member_id,
        estimated_tokens,
        budget.current_usage,
        budget.monthly_limit,
    )
    return False, _BLOCKED_REPLY


def record_budget_after_llm(
    member_id: str,
    messages: list[Message],
    response_text: str,
    member_name: str | None = None,
    *,
    description: str | None = None,
) -> None:
    if not budget_enabled() or not member_id:
        return
    inp = estimate_tokens_from_messages(messages)
    out = estimate_tokens_from_text(response_text)
    tokens = inp + out
    tracker = BudgetTracker()
    tracker.check_and_reset_budget(member_id)
    desc = description or f"LLM call ({len(messages)} messages)"
    rec = tracker.record_usage(
        member_id,
        tokens,
        UsageType.LLM_CALL,
        description=desc,
        member_name=member_name,
    )
    if rec is None:
        logger.warning("budget record_usage dropped for member=%s tokens=%s", member_id, tokens)


__all__ = [
    "budget_enabled",
    "check_budget_before_llm",
    "estimate_tokens_from_messages",
    "estimate_tokens_from_text",
    "llm_preflight_estimate",
    "record_budget_after_llm",
]
