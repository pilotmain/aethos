# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Agent runtime: manifest, sessions_spawn, background_heartbeat."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.core.db import SessionLocal, ensure_schema
from app.core.config import get_settings
from app.models.user import User
from app.services.agent_runtime.heartbeat import background_heartbeat
from app.services.agent_runtime.chat_tools import (
    clean_task_for_spawn,
    dedupe_session_specs,
    detect_valid_bounded_mission,
)
from app.services.agent_runtime.sessions import sessions_spawn
from app.services.agent_runtime.tool_registry import format_tools_prompt_block, load_tool_manifest


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


def test_tool_manifest_loads(runtime_env) -> None:
    m = load_tool_manifest()
    assert m.get("version") == "1.0"
    names = {t["name"] for t in m.get("tools", [])}
    assert "sessions_spawn" in names
    assert "background_heartbeat" in names


def test_format_tools_prompt_block_lists_tools(runtime_env) -> None:
    b = format_tools_prompt_block()
    assert "sessions_spawn" in b


def test_spawn_dedupes_duplicate_handles(runtime_env, db_session) -> None:
    uid = f"rt_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    payload = {
        "requested_by": uid,
        "goal": "Investigate the codebase structure",
        "sessions": [
            {
                "agent_handle": "research-analyst",
                "role": "research",
                "task": "First task line that is long enough here",
            },
            {
                "agent_handle": "research-analyst",
                "role": "research",
                "task": "Second duplicate handle wins if longer task text here",
            },
        ],
        "timebox_minutes": 60,
        "approval_policy": {"mode": "plan_only"},
    }
    out = sessions_spawn(db_session, user_id=uid, payload=payload)
    assert len(out["assignments"]) == 1


def test_clean_task_strips_instruction_headers() -> None:
    raw = "Dashboard:\nInstruction:\n\nDo the real work here with enough chars."
    assert "Dashboard" not in clean_task_for_spawn(raw)
    assert "real work" in clean_task_for_spawn(raw)


def test_bounded_mission_parses_at_handle_line() -> None:
    text = (
        '@boss execute bounded mission\n\n## Dashboard\n\nMission: "Goal"\n\n'
        "@researcher-pro: Summarize the repo with at least five characters.\n"
        "single-cycle supervised bounded mission team initialization"
    )
    m = detect_valid_bounded_mission(text)
    assert m is not None
    specs = dedupe_session_specs(list(m["sessions_specs"]))
    assert len(specs) == 1
    assert specs[0]["agent_handle"] == "researcher_pro"


def test_sessions_spawn_creates_assignments(runtime_env, db_session) -> None:
    uid = f"rt_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    payload = {
        "requested_by": uid,
        "goal": "Investigate the codebase structure",
        "sessions": [
            {
                "agent_handle": "research-analyst",
                "role": "research",
                "task": "Summarize repository layout and key modules",
            }
        ],
        "timebox_minutes": 60,
        "approval_policy": {"mode": "plan_only"},
    }
    out = sessions_spawn(db_session, user_id=uid, payload=payload)
    assert out["ok"] is True
    assert out["spawn_group_id"].startswith("spawn_")
    assert len(out["assignments"]) == 1
    assert out["assignments"][0]["assignment_id"] > 0


def test_background_heartbeat_writes_and_updates_assignment(runtime_env, db_session) -> None:
    uid = f"rt_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    payload_spawn = {
        "requested_by": uid,
        "goal": "Heartbeat test goal here",
        "sessions": [
            {
                "agent_handle": "research-analyst",
                "role": "r",
                "task": "Do something concrete here",
            }
        ],
        "timebox_minutes": 30,
        "approval_policy": {"mode": "plan_only"},
    }
    sp = sessions_spawn(db_session, user_id=uid, payload=payload_spawn)
    aid = sp["assignments"][0]["assignment_id"]
    hb = {
        "agent_handle": "research-analyst",
        "assignment_id": aid,
        "status": "running",
        "message": "Coordinating research and QA review.",
    }
    r1 = background_heartbeat(db_session, user_id=uid, payload=hb)
    assert r1["ok"] is True
    with pytest.raises(ValueError, match="rate limited"):
        background_heartbeat(db_session, user_id=uid, payload=hb)


@patch("app.services.agent_runtime.heartbeat._MIN_INTERVAL_SEC", 0.0)
def test_heartbeat_without_rate_block(runtime_env, db_session) -> None:
    uid = f"rt_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    hb = {
        "agent_handle": "research-analyst",
        "assignment_id": None,
        "status": "running",
        "message": "Coordinating.",
    }
    background_heartbeat(db_session, user_id=uid, payload=hb)
    background_heartbeat(db_session, user_id=uid, payload=hb)


def test_spawn_requires_matching_requested_by(runtime_env, db_session) -> None:
    uid = f"rt_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    payload = {
        "requested_by": "other_user",
        "goal": "Some goal that is long enough",
        "sessions": [
            {
                "agent_handle": "research-analyst",
                "role": "r",
                "task": "Task text that is long enough",
            }
        ],
        "timebox_minutes": 30,
        "approval_policy": {"mode": "plan_only"},
    }
    with pytest.raises(ValueError, match="requested_by"):
        sessions_spawn(db_session, user_id=uid, payload=payload)


def test_spawn_rejects_bad_policy_without_execution(runtime_env, db_session, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "regulated")
    monkeypatch.setenv("NEXA_APPROVALS_ENABLED", "true")
    monkeypatch.setenv("NEXA_HOST_EXECUTOR_ENABLED", "false")
    get_settings.cache_clear()
    uid = f"rt_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    payload = {
        "requested_by": uid,
        "goal": "Some goal that is long enough",
        "sessions": [
            {
                "agent_handle": "research-analyst",
                "role": "r",
                "task": "Task text that is long enough",
            }
        ],
        "timebox_minutes": 30,
        "approval_policy": {"mode": "approval_required_for_tools"},
    }
    try:
        with pytest.raises(ValueError, match="execution backends"):
            sessions_spawn(db_session, user_id=uid, payload=payload)
    finally:
        get_settings.cache_clear()
