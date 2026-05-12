# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 47E — cap autonomy fan-out using pending-queue depth and daily token load."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.autonomy import NexaAutonomousTask
from app.services.token_economy.budget import snapshot_for_user


def autonomy_rate_control(db: Session | None, user_id: str | None) -> dict[str, Any]:
    """Return whether new autonomy work should run for this user."""
    uid = (user_id or "").strip()
    if not uid:
        return {"allowed": True, "reason": None, "pending_tasks": 0, "tokens_today": None}

    s = get_settings()
    max_pending = int(getattr(s, "nexa_autonomy_max_pending_tasks", 48) or 48)
    max_tokens = int(getattr(s, "nexa_autonomy_daily_token_ceiling", 400_000) or 400_000)

    pending = 0
    if db is not None:
        try:
            pending = int(
                db.scalar(
                    select(func.count())
                    .select_from(NexaAutonomousTask)
                    .where(NexaAutonomousTask.user_id == uid, NexaAutonomousTask.state == "pending")
                )
                or 0
            )
        except Exception:
            pending = 0

    tok = snapshot_for_user(uid)
    tokens_today = int(tok.get("tokens_sent_today") or 0)

    if pending >= max_pending:
        return {
            "allowed": False,
            "reason": "pending_queue_cap",
            "pending_tasks": pending,
            "max_pending": max_pending,
            "tokens_today": tokens_today,
        }
    if tokens_today >= max_tokens:
        return {
            "allowed": False,
            "reason": "daily_token_ceiling",
            "pending_tasks": pending,
            "tokens_today": tokens_today,
            "max_tokens": max_tokens,
        }

    return {
        "allowed": True,
        "reason": None,
        "pending_tasks": pending,
        "tokens_today": tokens_today,
        "phase": 47,
    }


__all__ = ["autonomy_rate_control"]
