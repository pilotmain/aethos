"""Deterministic swarm worker completes chained assignments in developer mode."""

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
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "developer")
    monkeypatch.setenv("NEXA_APPROVALS_ENABLED", "false")
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


def test_worker_chains_researcher_then_dependent(runtime_env, db_session) -> None:
    uid = f"wk_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    t1 = "find 3 breakthroughs with enough characters here."
    t2 = "write forecast based on @researcher-pro output with enough characters."
    payload = {
        "requested_by": uid,
        "goal": "Robotics Research",
        "sessions": [
            {"agent_handle": "researcher-pro", "role": "Worker", "task": t1},
            {
                "agent_handle": "analyst-pro",
                "role": "Worker",
                "task": t2,
                "depends_on": ["researcher-pro"],
            },
        ],
        "timebox_minutes": 60,
        "approval_policy": {"mode": "plan_only"},
    }
    out = sessions_spawn(db_session, user_id=uid, payload=payload)
    assert out["ok"] is True
    aids = [x["assignment_id"] for x in out["assignments"]]
    r1 = db_session.get(AgentAssignment, aids[0])
    r2 = db_session.get(AgentAssignment, aids[1])
    assert r1 is not None and r2 is not None
    assert r1.status == "completed"
    assert r2.status == "completed"
    assert isinstance(r1.output_json, dict)
    assert isinstance(r2.output_json, dict)
