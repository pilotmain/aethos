"""sessions_spawn persists assignment titles equal to spawn task text."""

from __future__ import annotations

import uuid

import pytest

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.models.agent_team import AgentAssignment
from app.models.user import User
from app.services.agent_runtime.sessions import sessions_spawn


@pytest.fixture
def runtime_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_AGENT_TOOLS_ENABLED", "true")
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "regulated")
    monkeypatch.setenv("NEXA_APPROVALS_ENABLED", "true")
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


def test_assignment_title_equals_task_text(runtime_env, db_session) -> None:
    uid = f"spawn_exact_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    task = "find 3 breakthroughs in autonomous robotics."
    payload = {
        "requested_by": uid,
        "goal": "Robotics Research",
        "sessions": [
            {
                "agent_handle": "researcher-pro",
                "role": "Worker",
                "task": task,
            }
        ],
        "timebox_minutes": 60,
        "approval_policy": {"mode": "plan_only"},
    }
    out = sessions_spawn(db_session, user_id=uid, payload=payload)
    assert out["ok"] is True
    aid = out["assignments"][0]["assignment_id"]
    row = db_session.get(AgentAssignment, aid)
    assert row is not None
    assert row.title == task[:500]
