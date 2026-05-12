# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Unit tests for in-memory agent registry (Week 4 Phase 1)."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from app.services.sub_agent_registry import AgentRegistry, AgentStatus, SubAgent


class _S:
    """Minimal settings stub for registry tests."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        max_per_chat: int = 5,
        idle_timeout: int = 3600,
    ) -> None:
        self.nexa_agent_orchestration_enabled = enabled
        self.nexa_agent_max_per_chat = max_per_chat
        self.nexa_agent_idle_timeout_seconds = idle_timeout


@pytest.fixture
def registry() -> AgentRegistry:
    AgentRegistry.reset()
    return AgentRegistry()


def test_spawn_agent_disabled(registry: AgentRegistry) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S(enabled=False)):
        assert registry.spawn_agent("test-agent", "git", "chat123") is None


def test_spawn_agent_success(registry: AgentRegistry) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S()):
        agent = registry.spawn_agent("git-agent", "git", "chat123")
    assert agent is not None
    assert agent.name == "git-agent"
    assert agent.domain == "git"
    assert agent.parent_chat_id == "chat123"
    assert agent.status == AgentStatus.IDLE
    assert len(agent.capabilities) > 0


def test_spawn_agent_max_limit(registry: AgentRegistry) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S(max_per_chat=2)):
        a1 = registry.spawn_agent("agent1", "git", "chat123")
        a2 = registry.spawn_agent("agent2", "vercel", "chat123")
        assert a1 is not None and a2 is not None
        assert registry.spawn_agent("agent3", "railway", "chat123") is None


def test_spawn_agent_duplicate_name(registry: AgentRegistry) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S()):
        assert registry.spawn_agent("same-name", "git", "chat123") is not None
        assert registry.spawn_agent("same-name", "vercel", "chat123") is None


def test_get_agent(registry: AgentRegistry) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S()):
        agent = registry.spawn_agent("test", "git", "chat123")
        got = registry.get_agent(agent.id)
    assert got is not None and got.id == agent.id and got.name == "test"


def test_get_agent_by_name(registry: AgentRegistry) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S()):
        registry.spawn_agent("my-agent", "git", "chat123")
        assert registry.get_agent_by_name("my-agent", "chat123") is not None
        assert registry.get_agent_by_name("my-agent", "chat456") is None


def test_list_agents(registry: AgentRegistry) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S(max_per_chat=10)):
        registry.spawn_agent("agent1", "git", "chat123")
        registry.spawn_agent("agent2", "vercel", "chat123")
        registry.spawn_agent("agent3", "railway", "chat456")
    assert len(registry.list_agents("chat123")) == 2
    assert len(registry.list_agents()) == 3


def test_update_status(registry: AgentRegistry) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S()):
        agent = registry.spawn_agent("test", "git", "chat123")
        assert registry.update_status(agent.id, AgentStatus.BUSY) is True
        assert agent.status == AgentStatus.BUSY
    assert registry.update_status("invalid", AgentStatus.ERROR) is False


def test_terminate_agent(registry: AgentRegistry) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S()):
        agent = registry.spawn_agent("test", "git", "chat123")
        assert registry.terminate_agent(agent.id) is True
        assert agent.status == AgentStatus.TERMINATED
        assert registry.get_agent(agent.id) is not None


def test_cleanup_idle_agents(registry: AgentRegistry) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S(idle_timeout=10)):
        agent = registry.spawn_agent("test", "git", "chat123")
    agent.last_active = 0.0
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S(idle_timeout=10)), patch(
        "app.services.sub_agent_registry.time"
    ) as mt:
        mt.time.return_value = 100.0
        assert registry.cleanup_idle_agents() == 1
        assert agent.status == AgentStatus.TERMINATED


def test_get_stats(registry: AgentRegistry) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S()):
        registry.spawn_agent("agent1", "git", "chat123")
        registry.spawn_agent("agent2", "vercel", "chat123")
    s_chat = registry.get_stats("chat123")
    assert s_chat["total_agents"] == 2
    assert "git" in s_chat["domains"]
    assert "vercel" in s_chat["domains"]
    assert registry.get_stats()["total_agents"] == 2


def test_touch_agent(registry: AgentRegistry) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S()):
        agent = registry.spawn_agent("test", "git", "chat123")
        t0 = agent.last_active
        time.sleep(0.05)
        assert registry.touch_agent(agent.id) is True
        assert agent.last_active >= t0


def test_default_capabilities(registry: AgentRegistry) -> None:
    with patch("app.services.sub_agent_registry.get_settings", return_value=_S(max_per_chat=10)):
        git_agent = registry.spawn_agent("git", "git", "chat123")
        assert "commit" in git_agent.capabilities
        assert "push" in git_agent.capabilities
        vercel_agent = registry.spawn_agent("vercel", "vercel", "chat123")
        assert "deploy" in vercel_agent.capabilities
        assert "list" in vercel_agent.capabilities


def test_sub_agent_is_dataclass() -> None:
    a = SubAgent(
        id="x",
        name="n",
        domain="git",
        capabilities=["push"],
        parent_chat_id="c",
    )
    assert isinstance(a, SubAgent)
