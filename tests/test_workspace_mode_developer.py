# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""NEXA_WORKSPACE_MODE developer vs regulated prompts and runtime capability truth."""

from __future__ import annotations

import uuid

import pytest

from app.core.config import get_settings
from app.core.db import SessionLocal, ensure_schema
from app.models.user import User
from app.services.agent_runtime.boss_chat import try_boss_runtime_chat_turn
from app.services.custom_agents import BOSS_LLM_BASE, BOSS_LLM_DEVELOPER, DEVELOPER_WORKSPACE_HINT
from app.services.runtime_capabilities import (
    format_runtime_truth_prompt_block,
    get_runtime_truth,
    is_developer_workspace_mode,
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


def test_developer_base_directs_orchestrator_truth_not_false_refusal() -> None:
    low = BOSS_LLM_DEVELOPER.lower()
    assert "governed orchestrator" in low
    assert "sessions_spawn" in low
    assert "do not refuse" in low or "do **not** refuse" in BOSS_LLM_DEVELOPER.lower()


def test_regulated_base_still_has_safety_constraints() -> None:
    low = BOSS_LLM_BASE.lower()
    assert "nexa safety" in low or "approval" in low
    assert "unrestricted" in low or "unsupervised" in low


def test_developer_hint_warns_against_false_refusals() -> None:
    assert "read-only" in DEVELOPER_WORKSPACE_HINT.lower()
    assert "developer" in DEVELOPER_WORKSPACE_HINT.lower()


def test_get_runtime_truth_reflects_agent_tools(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_AGENT_TOOLS_ENABLED", "true")
    get_settings.cache_clear()
    try:
        t = get_runtime_truth()
        assert "sessions_spawn" in t
        assert "heartbeat" in t
        assert isinstance(t["sessions_spawn"], bool)
    finally:
        get_settings.cache_clear()


def test_runtime_truth_prompt_block_lists_keys() -> None:
    text = format_runtime_truth_prompt_block()
    assert "sessions_spawn" in text.lower()
    assert "background_heartbeat" in text.lower()


def test_valid_swarm_executes_in_developer_manual_example(runtime_env, db_session, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "developer")
    get_settings.cache_clear()
    try:
        assert is_developer_workspace_mode() is True
        uid = f"wm_{uuid.uuid4().hex[:12]}"
        db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
        db_session.commit()
        body = (
            "create bounded swarm with @researcher-pro and @analyst-pro "
            "to benchmark autonomy stacks"
        )
        r = try_boss_runtime_chat_turn(db_session, uid, body)
        assert r is not None
        assert "Spawn group created" in r
        assert "`spawn_" in r
    finally:
        get_settings.cache_clear()


def test_is_developer_workspace_mode_false_when_regulated(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "regulated")
    get_settings.cache_clear()
    try:
        assert is_developer_workspace_mode() is False
    finally:
        get_settings.cache_clear()
