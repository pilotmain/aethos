"""@boss deterministic runtime runs before custom-agent LLM (Web routing parity with Telegram)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.models.user import User
from app.models.user_agent import UserAgent
from app.services.custom_agent_routing import try_deterministic_custom_agent_turn


@pytest.fixture
def runtime_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_AGENT_TOOLS_ENABLED", "true")
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "developer")
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


def test_boss_mention_invokes_runtime_turn_before_llm(runtime_env, db_session) -> None:
    uid = f"rt_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.merge(
        UserAgent(
            owner_user_id=uid,
            agent_key="boss",
            display_name="Boss",
            description="Orchestrator",
            system_prompt="You are @boss.",
            allowed_tools_json="[]",
            safety_level="standard",
            is_active=True,
        )
    )
    db_session.commit()

    with patch(
        "app.services.agent_runtime.boss_chat.try_boss_runtime_chat_turn",
        return_value="__boss_det__",
    ) as boss_mock:
        with patch(
            "app.services.custom_agents.run_custom_user_agent",
        ) as llm_mock:
            r = try_deterministic_custom_agent_turn(
                db_session, uid, "@boss what tools do you have?"
            )
    boss_mock.assert_called_once()
    llm_mock.assert_not_called()
    assert r == "__boss_det__"
