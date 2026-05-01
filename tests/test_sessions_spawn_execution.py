"""sessions_spawn runs deterministically for @boss-style swarm phrases (real DB rows)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.models.agent_team import AgentAssignment
from app.models.user import User
from app.services.agent_runtime.boss_chat import try_boss_runtime_chat_turn
from app.services.response_sanitizer import sanitize_fake_sessions_spawn_reply


@pytest.fixture
def runtime_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_AGENT_TOOLS_ENABLED", "true")
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def db_session():
    ensure_schema()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _count_user_assignments(db, uid: str) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(AgentAssignment).where(AgentAssignment.user_id == uid)
        )
        or 0
    )


def test_bounded_vocab_and_handles_spawns_without_spawn_trigger_phrase(
    runtime_env, db_session
) -> None:
    """Bounded vocabulary + @handles must hit sessions_spawn even without 'create swarm' / sessions_spawn."""
    uid = f"sp_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    before = _count_user_assignments(db_session, uid)
    body = (
        "Supervised mission with @researcher-pro and @analyst-pro "
        "to investigate autonomous robotics benchmarks"
    )
    r = try_boss_runtime_chat_turn(db_session, uid, body)
    assert r is not None
    after = _count_user_assignments(db_session, uid)
    assert after > before
    assert "Spawn group created" in r
    assert "`spawn_" in r


def test_create_swarm_short_form_executes_sessions_spawn(runtime_env, db_session) -> None:
    uid = f"sp_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    before = _count_user_assignments(db_session, uid)
    body = (
        "create swarm with @researcher-pro and @analyst-pro "
        "to investigate autonomous robotics benchmarks"
    )
    r = try_boss_runtime_chat_turn(db_session, uid, body)
    assert r is not None
    after = _count_user_assignments(db_session, uid)
    assert after > before
    assert "Spawn group created" in r
    assert "`spawn_" in r
    assert "Awaiting backend confirmation" not in r
    assert "Invoking sessions_spawn" not in r


def test_spawn_failure_returns_error_not_success_tone(runtime_env, db_session) -> None:
    uid = f"sp_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    body = (
        "create swarm with @researcher-pro and @analyst-pro "
        "to investigate autonomous robotics benchmarks"
    )
    with patch(
        "app.services.agent_runtime.boss_chat.sessions_spawn",
        side_effect=RuntimeError("policy blocked"),
    ):
        r = try_boss_runtime_chat_turn(db_session, uid, body)
    assert r is not None
    assert "could not create the session group" in r.lower()
    assert "Spawn group created" not in r


def test_sanitizer_replaces_fake_sessions_spawn_llm_text() -> None:
    raw = "Invoking sessions_spawn now.\n\nAwaiting backend confirmation."
    out = sanitize_fake_sessions_spawn_reply(
        raw,
        user_text="@boss create swarm with @a and @b",
    )
    assert "Awaiting backend confirmation" not in out
    assert "Invoking sessions_spawn" not in out.lower()
    assert "simulated" in out.lower()
