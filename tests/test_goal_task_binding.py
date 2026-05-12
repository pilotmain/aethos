# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 47B — goals persist with execution children linked via goal_id."""

from __future__ import annotations

from sqlalchemy import select

from app.core.config import get_settings
from app.models.autonomy import NexaAutonomousTask
from app.services.autonomy.goal_engine import generate_and_persist_goals
from app.services.memory.memory_store import MemoryStore


def test_goal_spawn_rows_have_goal_id(db_session, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_GOAL_ENGINE_ENABLED", "true")
    monkeypatch.setenv("NEXA_AUTONOMOUS_MODE", "true")
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path / "mem"))
    get_settings.cache_clear()
    try:
        uid = f"bind_{__import__('uuid').uuid4().hex[:10]}"
        ms = MemoryStore()
        for i in range(25):
            ms.append_entry(uid, kind="note", title=f"n-{i}", body_md="x")
        generate_and_persist_goals(db_session, uid)
        rows = list(db_session.scalars(select(NexaAutonomousTask).where(NexaAutonomousTask.user_id == uid)).all())
        spawned = [r for r in rows if getattr(r, "origin", None) == "goal_spawn"]
        assert spawned
        for s in spawned:
            assert getattr(s, "goal_id", None)
            parent = db_session.get(NexaAutonomousTask, s.goal_id)
            assert parent is not None
            assert getattr(parent, "origin", None) == "goal_engine"
    finally:
        monkeypatch.delenv("NEXA_GOAL_ENGINE_ENABLED", raising=False)
        monkeypatch.delenv("NEXA_AUTONOMOUS_MODE", raising=False)
        monkeypatch.delenv("NEXA_MEMORY_DIR", raising=False)
        get_settings.cache_clear()
