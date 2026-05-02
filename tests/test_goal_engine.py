"""Phase 46D — autonomous goal generation."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.autonomy.goal_engine import generate_and_persist_goals
from app.services.memory.memory_store import MemoryStore


def test_goal_engine_disabled_by_default(db_session, monkeypatch) -> None:
    monkeypatch.delenv("NEXA_GOAL_ENGINE_ENABLED", raising=False)
    get_settings.cache_clear()
    try:
        uid = f"goal_off_{__import__('uuid').uuid4().hex[:8]}"
        assert generate_and_persist_goals(db_session, uid) == []
    finally:
        get_settings.cache_clear()


def test_goal_engine_inserts_tasks_when_enabled(db_session, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_GOAL_ENGINE_ENABLED", "true")
    monkeypatch.setenv("NEXA_AUTONOMOUS_MODE", "true")
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path / "mem"))
    get_settings.cache_clear()
    try:
        uid = f"goal_on_{__import__('uuid').uuid4().hex[:8]}"
        ms = MemoryStore()
        for i in range(25):
            ms.append_entry(uid, kind="note", title=f"note-{i}", body_md="body")
        ids = generate_and_persist_goals(db_session, uid)
        assert len(ids) >= 1
        from sqlalchemy import select

        from app.models.autonomy import NexaAutonomousTask

        rows = list(db_session.scalars(select(NexaAutonomousTask).where(NexaAutonomousTask.user_id == uid)).all())
        origins = {getattr(r, "origin", None) for r in rows}
        assert "goal_engine" in origins
    finally:
        monkeypatch.delenv("NEXA_GOAL_ENGINE_ENABLED", raising=False)
        monkeypatch.delenv("NEXA_AUTONOMOUS_MODE", raising=False)
        monkeypatch.delenv("NEXA_MEMORY_DIR", raising=False)
        get_settings.cache_clear()


def test_mission_control_phase46_slice(db_session) -> None:
    from app.services.mission_control.nexa_next_state import build_execution_snapshot

    uid = f"mc_p46_{__import__('uuid').uuid4().hex[:8]}"
    snap = build_execution_snapshot(db_session, user_id=uid)
    assert "phase46" in snap
    p46 = snap["phase46"]
    assert "goals" in p46
    assert "agent_intel" in p46
    assert p46.get("system_efficiency", {}).get("phase") == 46
