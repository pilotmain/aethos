"""Chat-layer wiring for @boss: deterministic sessions_spawn + background_heartbeat."""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import desc, select

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.agent_runtime.boss_chat import try_boss_runtime_chat_turn
from app.services.agent_runtime.paths import heartbeats_json_path


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


def _latest_tool_audit(db, uid: str) -> AuditLog | None:
    return db.scalars(
        select(AuditLog)
        .where(
            AuditLog.event_type == "agent_runtime.tool_invoked",
            AuditLog.user_id == uid,
        )
        .order_by(desc(AuditLog.id))
        .limit(1)
    ).first()


@patch("app.services.agent_runtime.heartbeat._MIN_INTERVAL_SEC", 0.0)
def test_boss_heartbeat_chat_updates_files_and_audits(runtime_env, db_session) -> None:
    uid = f"chat_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    body = "record heartbeat: coordinating research and QA review."
    r = try_boss_runtime_chat_turn(db_session, uid, body)
    assert r is not None
    assert "Heartbeat recorded" in r
    assert "running" in r.lower()
    assert "Mission Control" in r
    path = heartbeats_json_path()
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "heartbeats" in data
    blob = json.dumps(data["heartbeats"])
    assert "boss" in blob
    row = _latest_tool_audit(db_session, uid)
    assert row is not None
    md = row.metadata_json or {}
    assert md.get("tool") == "background_heartbeat"
    assert md.get("source") == "chat"


def test_boss_spawn_chat_creates_assignments(runtime_env, db_session) -> None:
    uid = f"chat_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    body = (
        "create a bounded agent swarm with @research-analyst and @qa "
        "to investigate autonomous robotics"
    )
    r = try_boss_runtime_chat_turn(db_session, uid, body)
    assert r is not None
    assert "Spawn group created" in r
    assert "`spawn_" in r
    assert "#" in r
    row = _latest_tool_audit(db_session, uid)
    assert row is not None
    assert (row.metadata_json or {}).get("tool") == "sessions_spawn"


def test_boss_spawn_failure_no_success_claim(runtime_env, db_session) -> None:
    uid = f"chat_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    body = "create a bounded agent swarm with @research-analyst and @qa to test failure path"
    with patch(
        "app.services.agent_runtime.boss_chat.sessions_spawn",
        side_effect=RuntimeError("backend unavailable"),
    ):
        r = try_boss_runtime_chat_turn(db_session, uid, body)
    assert r is not None
    assert "I could not create the session group" in r
    assert "Spawn group created" not in r
    assert "Sessions started" not in r


def test_boss_spawn_tools_off_returns_guidance(
    tmp_path, monkeypatch: pytest.MonkeyPatch, db_session
) -> None:
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_AGENT_TOOLS_ENABLED", "false")
    get_settings.cache_clear()
    try:
        uid = f"chat_{uuid.uuid4().hex[:12]}"
        body = "create a bounded agent swarm with @foo and @bar to do something"
        r = try_boss_runtime_chat_turn(db_session, uid, body)
        assert r is not None
        assert "Runtime tools are not enabled" in r
        assert "sessions_spawn" in r.lower()
    finally:
        get_settings.cache_clear()


def test_boss_bounded_swarm_invokes_spawn_no_i_can_request(runtime_env, db_session) -> None:
    uid = f"chat_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    body = (
        "create a bounded agent swarm with @research-analyst and @qa "
        "to investigate emerging robotics tech. Do not write files."
    )
    r = try_boss_runtime_chat_turn(db_session, uid, body)
    assert r is not None
    assert "Spawn group created" in r
    assert "I can request" not in r


def test_boss_spawn_missing_handles_no_backend(runtime_env, db_session) -> None:
    uid = f"chat_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    with patch("app.services.agent_runtime.boss_chat.sessions_spawn") as sp:
        r = try_boss_runtime_chat_turn(
            db_session,
            uid,
            "create a bounded agent swarm to investigate robotics",
        )
        sp.assert_not_called()
    assert r is not None
    assert "Which agents" in r


def test_boss_spawn_missing_goal_no_backend(runtime_env, db_session) -> None:
    uid = f"chat_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    with patch("app.services.agent_runtime.boss_chat.sessions_spawn") as sp:
        r = try_boss_runtime_chat_turn(
            db_session,
            uid,
            "create agent sessions with @research-analyst and @qa",
        )
        sp.assert_not_called()
    assert r is not None
    assert "mission goal" in r.lower()


def test_recurring_refusal_does_not_call_sessions_spawn(
    runtime_env, db_session
) -> None:
    uid = f"chat_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    with patch("app.services.agent_runtime.boss_chat.sessions_spawn") as sp:
        r = try_boss_runtime_chat_turn(
            db_session,
            uid,
            "run agents every 12 hours overnight without me",
        )
        sp.assert_not_called()
    assert r is not None
    assert "bounded" in r.lower() or "supervised" in r.lower()


@patch("app.services.agent_runtime.heartbeat._MIN_INTERVAL_SEC", 0.0)
def test_boss_heartbeat_colon_prefix(runtime_env, db_session) -> None:
    uid = f"chat_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    r = try_boss_runtime_chat_turn(
        db_session,
        uid,
        "heartbeat: coordinating robotics research.",
    )
    assert r is not None
    assert "Heartbeat recorded" in r
    assert "Mission Control" in r


def test_spawn_sessions_trigger(runtime_env, db_session) -> None:
    uid = f"chat_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    body = "spawn sessions with @research-analyst and @qa to investigate robotics stack"
    r = try_boss_runtime_chat_turn(db_session, uid, body)
    assert r is not None
    assert "Spawn group created" in r

