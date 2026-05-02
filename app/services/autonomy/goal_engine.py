"""Phase 46D — higher-level goals decomposed into autonomous tasks."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.autonomy import NexaAutonomousTask
from app.services.memory.memory_store import MemoryStore


def _pending_title_exists(db: Session, user_id: str, title: str) -> bool:
    t = title.strip()[:8000]
    if not t:
        return True
    row = db.scalar(
        select(NexaAutonomousTask).where(
            NexaAutonomousTask.user_id == user_id,
            NexaAutonomousTask.title == t,
            NexaAutonomousTask.state == "pending",
        )
    )
    return row is not None


def generate_and_persist_goals(db: Session, user_id: str) -> list[str]:
    """
    Derive a small set of strategic goals from memory depth and enqueue them.

    Goals are stored as :class:`NexaAutonomousTask` rows with ``origin='goal_engine'``.
    """
    if not getattr(get_settings(), "nexa_goal_engine_enabled", False):
        return []
    if not getattr(get_settings(), "nexa_autonomous_mode", False):
        return []

    uid = (user_id or "").strip()
    if not uid:
        return []

    mem_n = len(MemoryStore().list_entries(uid, limit=400))
    goals: list[str] = []
    if mem_n > 22:
        goals.append("Goal: consolidate long-term memory themes and archive stale notes")
    goals.append("Goal: strengthen automated test coverage for recently touched areas")
    if mem_n > 40:
        goals.append("Goal: produce a concise system health digest from recent failures")

    inserted: list[str] = []
    for g in goals[:3]:
        if _pending_title_exists(db, uid, g):
            continue
        tid = str(uuid.uuid4())
        row = NexaAutonomousTask(
            id=tid,
            user_id=uid,
            title=g[:8000],
            state="pending",
            priority=88,
            auto_generated=True,
            origin="goal_engine",
            context_json=json.dumps(
                {"nexa_task": {"type": "goal", "context": {"source": "goal_engine"}}, "phase": 46},
                ensure_ascii=False,
            )[:50_000],
        )
        db.add(row)
        inserted.append(tid)
    if inserted:
        db.commit()
    return inserted


__all__ = ["generate_and_persist_goals"]
