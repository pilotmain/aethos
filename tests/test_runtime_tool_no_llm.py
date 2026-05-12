# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""handle_runtime_tool_turn executes sessions_spawn without LLM (bounded mission dict path)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.models.user import User
from app.services.agent_runtime.chat_tools import detect_valid_bounded_mission, handle_runtime_tool_turn


SHORT_MISSION = (
    "@boss execute bounded mission with @researcher-pro and @analyst-pro"
)


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


def test_short_bounded_mission_detected() -> None:
    m = detect_valid_bounded_mission(SHORT_MISSION)
    assert m is not None
    assert m["goal"]
    assert len(m["sessions_specs"]) >= 2


@patch("app.services.agent_runtime.sessions.sessions_spawn")
def test_handle_runtime_tool_turn_calls_spawn_once(mock_spawn, runtime_env, db_session) -> None:
    uid = f"rt_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    mock_spawn.return_value = {
        "spawn_group_id": "spawn_test123456",
        "assignments": [
            {"assignment_id": 1, "agent_handle": "researcher-pro", "status": "queued"},
            {"assignment_id": 2, "agent_handle": "analyst-pro", "status": "queued"},
        ],
    }
    with patch(
        "app.services.agent_runtime.chat_tools.try_record_initial_spawn_heartbeat",
        return_value="**Initial heartbeat recorded.**",
    ):
        out = handle_runtime_tool_turn(db_session, user_id=uid, text=SHORT_MISSION)
    assert out is not None
    assert out.get("ok") is True
    mock_spawn.assert_called_once()
    assert "spawn_test123456" in (out.get("reply") or "")


def test_handle_runtime_tool_turn_none_when_no_mission(runtime_env, db_session) -> None:
    uid = f"rt_{uuid.uuid4().hex[:12]}"
    assert handle_runtime_tool_turn(db_session, user_id=uid, text="hello world") is None
