# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 46D / 47B — higher-level goals and bound execution tasks per goal."""

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
    Derive a small set of strategic goals from memory depth and enqueue them,
    each with at least one bound execution child task (``goal_id`` link).
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
            goal_id=None,
            context_json=json.dumps(
                {
                    "nexa_task": {"type": "goal", "context": {"source": "goal_engine"}},
                    "phase": 47,
                    "is_goal_root": True,
                },
                ensure_ascii=False,
            )[:50_000],
        )
        db.add(row)
        short = g.replace("Goal: ", "").strip()[:200]
        child_title = f"Execute goal work ({tid[:8]}): {short}"
        if not _pending_title_exists(db, uid, child_title):
            cid = str(uuid.uuid4())
            child = NexaAutonomousTask(
                id=cid,
                user_id=uid,
                title=child_title,
                state="pending",
                priority=80,
                auto_generated=True,
                origin="goal_spawn",
                goal_id=tid,
                context_json=json.dumps(
                    {
                        "nexa_task": {
                            "type": "system",
                            "context": {
                                "parent_goal_id": tid,
                                "source": "goal_engine_spawn",
                                "goal_binding": True,
                            },
                        },
                        "goal_binding": True,
                        "phase": 47,
                    },
                    ensure_ascii=False,
                )[:50_000],
            )
            db.add(child)
            inserted.append(cid)
        inserted.append(tid)
    if inserted:
        db.commit()
    return inserted


__all__ = ["generate_and_persist_goals"]
