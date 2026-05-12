# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control dashboard-mode prompts must not trigger sessions_spawn."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.models.agent_team import AgentAssignment
from app.models.user import User
from app.services.agent_runtime.boss_chat import try_boss_runtime_chat_turn
from app.services.agent_runtime.chat_tools import detect_bounded_mission_structure, detect_valid_bounded_mission
from app.services.mission_control.mode import is_mission_control_mode_prompt, mission_control_mode_json_path


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


DASHBOARD_SHORT = (
    "@boss initialize Mission Control dashboard mode for this workspace\n\n"
    "Use structured responses only.\n"
)


def test_dashboard_mode_prompt_does_not_spawn(runtime_env, db_session) -> None:
    uid = f"web_dm_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()

    with patch("app.services.agent_runtime.boss_chat.sessions_spawn") as sp:
        r = try_boss_runtime_chat_turn(db_session, uid, DASHBOARD_SHORT)

    sp.assert_not_called()
    assert r is not None
    assert "No agent sessions were spawned" in r or "dashboard" in r.lower()
    rows = db_session.query(AgentAssignment).filter(AgentAssignment.user_id == uid).all()
    assert len(rows) == 0


def test_dashboard_initializes_files(runtime_env, db_session) -> None:
    uid = f"web_dm_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()

    r = try_boss_runtime_chat_turn(db_session, uid, DASHBOARD_SHORT)
    assert r is not None

    cfg = mission_control_mode_json_path()
    assert cfg.is_file(), str(cfg)
    body = cfg.read_text()
    assert "dashboard" in body.lower()
    mc = Path(runtime_env) / "reports" / "mission_control.md"
    assert mc.is_file()
    assert "Agent Swarm" in mc.read_text()


def test_real_bounded_mission_still_spawns(runtime_env, db_session) -> None:
    uid = f"web_dm_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()

    mission = """
@boss execute bounded mission.
@researcher-pro: find 3 breakthroughs in autonomous robotics.
@analyst-pro: write a 3-paragraph forecast.
single-cycle.
""".strip()

    with patch("app.services.agent_runtime.boss_chat.sessions_spawn") as sp:
        r = try_boss_runtime_chat_turn(db_session, uid, mission)

    sp.assert_called_once()
    assert r is not None
    assert "Spawn group created" in r


def test_mixed_dashboard_and_execute_mission_split(runtime_env, db_session) -> None:
    uid = f"web_dm_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()

    text = "initialize dashboard mode and execute robotics mission"

    with patch("app.services.agent_runtime.boss_chat.sessions_spawn") as sp:
        r = try_boss_runtime_chat_turn(db_session, uid, text)

    sp.assert_not_called()
    assert r is not None
    assert "Send the mission task next" in r


def test_visual_formatting_block_not_a_bounded_mission() -> None:
    blob = """
@boss

Visual formatting:
Use structured blocks.

[MISSION]
Title: Robotics Intelligence Swarm
Status: Running

Authorization & Scope:
bounded, single-cycle supervised mission.

Team Initialization:
Use sessions_spawn() to initialize:
""".strip()
    assert detect_valid_bounded_mission(blob) is None
    assert detect_bounded_mission_structure(blob) is None


def test_detector_true_for_dashboard_phrases() -> None:
    assert is_mission_control_mode_prompt(DASHBOARD_SHORT) is True
