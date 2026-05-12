# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""@boss: tool list messaging and prompt strings (no stale text-only refusals when tools exist)."""

from __future__ import annotations

import uuid

import pytest

from app.core.config import get_settings
from app.core.db import ensure_schema, SessionLocal
from app.models.user import User
from app.services.agent_runtime.boss_chat import format_tools_list_reply, try_boss_runtime_chat_turn
from app.services.custom_agents import BOSS_LLM_BASE, BOSS_TOOLS_DISABLED_LINE, NEXA_BASE


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


def test_format_tools_list_when_disabled(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_AGENT_TOOLS_ENABLED", "false")
    get_settings.cache_clear()
    try:
        r = format_tools_list_reply()
        assert "Runtime tools are not enabled" in r
    finally:
        get_settings.cache_clear()


def test_format_tools_list_when_enabled(runtime_env) -> None:
    r = format_tools_list_reply()
    assert "sessions_spawn" in r
    assert "background_heartbeat" in r
    assert "Available governed tools" in r


def test_boss_llm_base_does_not_encode_legacy_refusals() -> None:
    stale = (
        "I have no sessions_spawn function",
        "I cannot spawn sub-agents",
        "I am text-only",
    )
    for s in stale:
        assert s.lower() not in BOSS_LLM_BASE.lower()


def test_tools_disabled_line_mentions_flag() -> None:
    assert "NEXA_AGENT_TOOLS_ENABLED=false" in BOSS_TOOLS_DISABLED_LINE


def test_nexa_base_still_mentions_text_only_for_non_boss() -> None:
    assert "text-only" in NEXA_BASE.lower()


def test_bounded_autonomy_reply(runtime_env, db_session) -> None:
    uid = f"boss_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    r = try_boss_runtime_chat_turn(
        db_session,
        uid,
        "run agents autonomously all night without my involvement",
    )
    assert r is not None
    low = r.lower()
    assert "bounded" in low or "governed" in low or "supervised" in low
    assert "unrestricted" in low or "without your involvement" in low


def test_recurring_unsupervised_refusal(runtime_env, db_session) -> None:
    uid = f"boss_{uuid.uuid4().hex[:12]}"
    db_session.merge(User(id=uid, name="T", timezone="UTC", is_new=False))
    db_session.commit()
    r = try_boss_runtime_chat_turn(
        db_session,
        uid,
        "run agents every 12 hours overnight without me",
    )
    assert r is not None
    low = r.lower()
    assert "recurring" in low or "unrestricted" in low
    assert "bounded" in low or "supervised" in low
