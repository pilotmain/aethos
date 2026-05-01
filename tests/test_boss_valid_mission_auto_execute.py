"""Bounded @boss missions: deterministic sessions_spawn without LLM confirmation loop."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.models.user import User
from app.services.agent_runtime.boss_chat import try_boss_runtime_chat_turn
from app.services.agent_runtime.chat_tools import detect_valid_bounded_mission
from app.services.response_sanitizer import sanitize_fake_sessions_spawn_reply


FULL_BOUNDED_MISSION = """
@boss execute System Mission: "Robotics Intelligence Swarm"

Authorization & Scope:
I am providing explicit human oversight for this mission.

Team Initialization:
Use sessions_spawn() to initialize:
@researcher-pro: identify 3 breakthrough technologies in Autonomous Robotics from the last 30 days.
@analyst-pro: write a 3-paragraph Market Impact Forecast based on the researcher's data.

Workflow:
@researcher-pro saves findings to /reports/tech_data.json.
@analyst-pro reads that file and outputs /reports/mission_control.md.

Heartbeat:
record heartbeat every 1 hour until completion.
This is a bounded, single-cycle mission.
""".strip()


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


def test_detect_valid_bounded_mission_parses_doc_example() -> None:
    m = detect_valid_bounded_mission(FULL_BOUNDED_MISSION)
    assert m is not None
    assert m["goal"] == "Robotics Intelligence Swarm"
    assert len(m["sessions_specs"]) == 2
    assert m["heartbeat_recurring_requested"] is True
    assert "/reports/tech_data.json" in (m.get("output_paths") or [])


def test_complete_mission_auto_executes_no_confirmation(runtime_env, db_session) -> None:
    uid = f"bm_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()

    captured: dict[str, object] = {}

    from app.services.agent_runtime.sessions import sessions_spawn as real_spawn

    def _spy(db, *, user_id: str, payload: dict) -> dict:
        captured["payload"] = payload
        return real_spawn(db, user_id=user_id, payload=payload)

    with patch(
        "app.services.agent_runtime.boss_chat.sessions_spawn",
        side_effect=_spy,
    ):
        r = try_boss_runtime_chat_turn(db_session, uid, FULL_BOUNDED_MISSION)

    assert r is not None
    assert "Spawn group created" in r
    assert "`spawn_" in r
    assert "#" in r
    pl = captured.get("payload")
    assert isinstance(pl, dict)
    assert pl.get("mission_contract") is not None
    low = r.lower()
    assert "should i proceed" not in low
    assert "please confirm" not in low


def test_missing_agents_clarifies(runtime_env, db_session) -> None:
    uid = f"bm_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    with patch("app.services.agent_runtime.boss_chat.sessions_spawn") as sp:
        r = try_boss_runtime_chat_turn(
            db_session,
            uid,
            "@boss execute bounded mission to research robotics",
        )
        sp.assert_not_called()
    assert r is not None
    assert "Which agents" in r


def test_missing_goal_clarifies(runtime_env, db_session) -> None:
    uid = f"bm_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    with patch("app.services.agent_runtime.boss_chat.sessions_spawn") as sp:
        r = try_boss_runtime_chat_turn(
            db_session,
            uid,
            "@boss create bounded swarm with @researcher-pro and @analyst-pro",
        )
        sp.assert_not_called()
    assert r is not None
    assert "mission goal" in r.lower()


def test_unbounded_recurring_refused(runtime_env, db_session) -> None:
    uid = f"bm_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    with patch("app.services.agent_runtime.boss_chat.sessions_spawn") as sp:
        r = try_boss_runtime_chat_turn(
            db_session,
            uid,
            "@boss run agents every hour forever without asking me",
        )
        sp.assert_not_called()
    assert r is not None
    low = r.lower()
    assert "bounded" in low or "supervised" in low


def test_sanitizer_replaces_confirmation_when_user_had_valid_mission() -> None:
    out = sanitize_fake_sessions_spawn_reply(
        "Should I proceed with the spawn request?",
        user_text=FULL_BOUNDED_MISSION,
    )
    assert "Should I proceed" not in out
    assert "chat_tools routing" in out.lower()


@patch("app.services.agent_runtime.heartbeat._MIN_INTERVAL_SEC", 0.0)
def test_mission_heartbeat_single_shot_wording(runtime_env, db_session) -> None:
    uid = f"bm_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    r = try_boss_runtime_chat_turn(db_session, uid, FULL_BOUNDED_MISSION)
    assert r is not None
    low = r.lower()
    assert "initial heartbeat" in low
    assert "single status heartbeat" in low
    assert "recurring" in low


def test_valid_mission_skips_llm_when_sessions_spawn_mocked(runtime_env, db_session) -> None:
    uid = f"bm_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    fake = MagicMock(
        return_value={
            "spawn_group_id": "spawn_deadbeef1234",
            "assignments": [
                {"assignment_id": 9, "agent_handle": "researcher-pro", "status": "queued"},
                {"assignment_id": 10, "agent_handle": "analyst-pro", "status": "queued"},
            ],
        }
    )
    with patch("app.services.agent_runtime.boss_chat.sessions_spawn", fake):
        r = try_boss_runtime_chat_turn(db_session, uid, FULL_BOUNDED_MISSION)
    fake.assert_called_once()
    assert r is not None
    assert "spawn_deadbeef1234" in r
    assert "#9" in r or "#10" in r
