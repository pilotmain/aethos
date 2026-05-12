# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Boss deterministic spawn lifecycle chat (lookup / continue)."""

from __future__ import annotations

import uuid

import pytest

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.models.user import User
from app.services.agent_runtime.boss_chat import try_spawn_lifecycle_chat_turn
from app.services.agent_runtime.sessions import sessions_spawn


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


@pytest.fixture
def spawned_group(runtime_env, db_session):
    uid = f"lc_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    payload = {
        "requested_by": uid,
        "goal": "investigate emerging robotics tech",
        "sessions": [
            {
                "agent_handle": "research-analyst",
                "role": "Worker",
                "task": "investigate emerging robotics tech — worker",
            },
            {
                "agent_handle": "qa",
                "role": "Reviewer",
                "task": "Review findings for: investigate emerging robotics tech",
            },
        ],
        "timebox_minutes": 60,
        "approval_policy": {"mode": "plan_only"},
    }
    out = sessions_spawn(db_session, user_id=uid, payload=payload)
    return uid, str(out["spawn_group_id"])


def test_continue_spawn_replies_without_clarification_questions(
    runtime_env, db_session, spawned_group, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.services.agent_runtime.heartbeat._MIN_INTERVAL_SEC",
        0.0,
    )
    uid, sgid = spawned_group
    msg = f"@boss continue spawn_group_id {sgid}"
    r = try_spawn_lifecycle_chat_turn(db_session, uid, msg)
    assert r is not None
    assert "I found" in r and sgid in r
    assert "What agents are involved" not in r
    assert "What is the current status" not in r
    assert "What is the mission" not in r


def test_continue_unknown_spawn(runtime_env, db_session) -> None:
    uid = f"lc_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    r = try_spawn_lifecycle_chat_turn(
        db_session,
        uid,
        "continue spawn_group_id spawn_deadbeef123456",
    )
    assert r is not None
    assert "could not find spawn group" in r.lower()


def test_spawn_context_routes_before_qa_persona(runtime_env, db_session, spawned_group) -> None:
    uid, sgid = spawned_group
    msg = (
        f"spawn_group_id: {sgid}\n"
        "assignment_ids:\n"
        "- 405 (@research_analyst)\n"
        f"- 406 (@qa)\n"
        f"status of spawn_group_id {sgid}"
    )
    r = try_spawn_lifecycle_chat_turn(db_session, uid, msg)
    assert r is not None
    assert sgid in r
    assert "#" in r


def test_status_only_no_heartbeat_required_phrase(runtime_env, db_session, spawned_group) -> None:
    uid, sgid = spawned_group
    r = try_spawn_lifecycle_chat_turn(
        db_session,
        uid,
        f"what is happening with {sgid}",
    )
    assert r is not None
    assert "Spawn group" in r
    assert "Goal:" in r
