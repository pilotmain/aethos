"""Spawn group lookup from AgentAssignment titles."""

from __future__ import annotations

import uuid

import pytest

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.models.user import User
from app.services.agent_runtime.paths import mission_control_md_path
from app.services.agent_runtime.spawn_state import (
    continue_spawn_group,
    get_spawn_group_state,
    normalize_spawn_group_id,
)
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


def test_normalize_spawn_group_id() -> None:
    assert normalize_spawn_group_id("ac16ad6baaf8").startswith("spawn_")
    assert normalize_spawn_group_id("spawn_ac16ad6baaf8") == "spawn_ac16ad6baaf8"


def test_get_spawn_group_state_loads_rows(runtime_env, db_session) -> None:
    uid = f"sg_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    payload = {
        "requested_by": uid,
        "goal": "investigate emerging robotics tech",
        "sessions": [
            {
                "agent_handle": "research-analyst",
                "role": "Worker",
                "task": "Investigate emerging robotics tech — focus area for research",
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
    sgid = str(out["spawn_group_id"])
    st = get_spawn_group_state(db_session, user_id=uid, spawn_group_id=sgid)
    assert st.get("ok") is True
    assert st["spawn_group_id"] == sgid
    assert len(st["assignments"]) >= 3
    assert "investigate emerging robotics tech" in (st.get("goal") or "")
    summ = st.get("summary") or {}
    assert sum(summ.values()) == len(st["assignments"])


def test_continue_spawn_group_writes_heartbeat_and_mission_control(
    runtime_env, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.services.agent_runtime.heartbeat._MIN_INTERVAL_SEC",
        0.0,
    )
    uid = f"sg_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    payload = {
        "requested_by": uid,
        "goal": "coordination test goal here long enough",
        "sessions": [
            {
                "agent_handle": "research-analyst",
                "role": "Worker",
                "task": "coordination test goal here long enough — focus",
            },
            {
                "agent_handle": "qa",
                "role": "Reviewer",
                "task": "Review findings for: coordination test goal here long enough",
            },
        ],
        "timebox_minutes": 60,
        "approval_policy": {"mode": "plan_only"},
    }
    out = sessions_spawn(db_session, user_id=uid, payload=payload)
    sgid = str(out["spawn_group_id"])
    cont = continue_spawn_group(db_session, user_id=uid, spawn_group_id=sgid)
    assert cont.get("heartbeat", {}).get("ok") is True
    p = mission_control_md_path()
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert sgid in text
    assert "Mission Control" in text or "Spawn group" in text


def test_get_spawn_group_state_unknown(runtime_env, db_session) -> None:
    uid = f"sg_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    st = get_spawn_group_state(db_session, user_id=uid, spawn_group_id="spawn_deadbeef999999")
    assert st.get("ok") is False
