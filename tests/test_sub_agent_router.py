# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Week 4 Phase 2 — sub-agent router (@mentions) and gateway helper."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.gateway.context import GatewayContext
from app.services.sub_agent_registry import AgentRegistry, AgentStatus
from app.services.sub_agent_router import (
    AgentRouter,
    orchestration_chat_key,
    resolve_agent_for_dispatch,
    try_extract_natural_language_sub_agent,
    try_sub_agent_gateway_turn,
)


class _S:
    nexa_agent_orchestration_enabled = True
    nexa_natural_agent_invocation = True
    nexa_agent_max_per_chat = 5
    nexa_agent_idle_timeout_seconds = 3600
    nexa_agent_orchestration_autoqueue = False
    nexa_sub_agent_auto_execute = False  # bare @mention → “ready” hint (tests expect stable copy)


class _NLoff(_S):
    nexa_natural_agent_invocation = False


class _Recover(_S):
    nexa_assignment_auto_recover = True
    nexa_assignment_auto_recover_wait_seconds = 0.0


class _Off:
    nexa_agent_orchestration_enabled = False
    nexa_agent_max_per_chat = 5
    nexa_agent_idle_timeout_seconds = 3600


@pytest.fixture
def router() -> AgentRouter:
    return AgentRouter()


@pytest.fixture
def registry() -> AgentRegistry:
    AgentRegistry.reset()
    return AgentRegistry()


def test_router_disabled(router: AgentRouter) -> None:
    with patch("app.services.sub_agent_router.get_settings", return_value=_Off()):
        result = router.route("@test hello", "chat123")
        assert result["handled"] is False


def test_try_gateway_turn_disabled() -> None:
    gctx = GatewayContext(user_id="u1", channel="web", extras={"web_session_id": "s1"})
    with patch("app.services.sub_agent_router.get_settings", return_value=_Off()):
        assert try_sub_agent_gateway_turn(gctx, "@x hi") is None


def test_parse_mention_start(router: AgentRouter) -> None:
    result = router._parse_mention("@git-agent deploy now")
    assert result is not None
    assert result[0] == "git-agent"
    assert result[1] == "deploy now"


def test_parse_mention_no_message(router: AgentRouter) -> None:
    result = router._parse_mention("@git-agent")
    assert result is not None
    assert result[0] == "git-agent"
    assert result[1] == ""


def test_parse_mention_not_found(router: AgentRouter) -> None:
    assert router._parse_mention("just plain text") is None


def test_orchestration_chat_key_web() -> None:
    gctx = GatewayContext(
        user_id="user-1",
        channel="web",
        extras={"web_session_id": "sess-a"},
    )
    assert orchestration_chat_key(gctx) == "web:user-1:sess-a"


def test_orchestration_chat_key_telegram() -> None:
    gctx = GatewayContext(
        user_id="user-1",
        channel="telegram",
        extras={"telegram_chat_id": "999"},
    )
    assert orchestration_chat_key(gctx) == "telegram:999"


def test_route_agent_not_found(registry: AgentRegistry, router: AgentRouter) -> None:
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_S()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_S()),
    ):
        result = router.route("@missing-agent deploy", "chat123")
        assert result["handled"] is True
        assert "was not found" in result["response"].lower() or "not found" in result["response"].lower()


def test_route_agent_found(registry: AgentRegistry, router: AgentRouter) -> None:
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_S()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_S()),
    ):
        agent = registry.spawn_agent("git-agent", "git", "chat123")
        assert agent is not None
        # No text after @name → readiness hint (no execution)
        result = router.route("@git-agent", "chat123", user_id="u1")
        assert result["handled"] is True
        assert "instruction" in result["response"].lower() or "ready" in result["response"].lower()
        assert result["agent_id"] == agent.id
        assert result["agent_name"] == "git-agent"


def test_route_busy_agent(registry: AgentRegistry, router: AgentRouter) -> None:
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_S()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_S()),
    ):
        agent = registry.spawn_agent("busy-agent", "git", "chat123")
        assert agent is not None
        registry.update_status(agent.id, AgentStatus.BUSY)
        result = router.route("@busy-agent deploy", "chat123")
        assert result["handled"] is True
        assert "busy" in result["response"].lower()


def test_route_terminated_agent_blocked_when_auto_recover_off(
    registry: AgentRegistry, router: AgentRouter
) -> None:
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_S()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_S()),
    ):
        agent = registry.spawn_agent("dead-agent", "git", "chat123")
        assert agent is not None
        registry.update_status(agent.id, AgentStatus.TERMINATED)
        result = router.route("@dead-agent deploy", "chat123")
        assert result["handled"] is True
        assert "terminated" in result["response"].lower()


def test_route_terminated_agent_auto_recover_then_execute(
    registry: AgentRegistry, router: AgentRouter
) -> None:
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_Recover()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_Recover()),
        patch("app.services.sub_agent_executor.AgentExecutor") as ex_cls,
    ):
        agent = registry.spawn_agent("revive-agent", "git", "chat123")
        assert agent is not None
        registry.update_status(agent.id, AgentStatus.TERMINATED)
        ex_cls.return_value.execute.return_value = "recovered_ok"
        result = router.route("@revive-agent ping", "chat123", user_id="u1")
        assert result["handled"] is True
        assert result["response"] == "recovered_ok"
        ex_cls.return_value.execute.assert_called_once()
        refreshed = registry.get_agent(agent.id)
        assert refreshed is not None
        assert refreshed.status == AgentStatus.IDLE


def test_extract_natural_language_ask_to(registry: AgentRegistry) -> None:
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_S()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_S()),
    ):
        registry.spawn_agent("git-agent", "git", "chat123")
        hit = try_extract_natural_language_sub_agent(
            "ask git-agent to run status check",
            "chat123",
            registry,
        )
        assert hit is not None
        assert hit[0].name == "git-agent"
        assert "status" in hit[1].lower()


def test_extract_natural_language_unknown_returns_none(registry: AgentRegistry) -> None:
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_S()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_S()),
    ):
        registry.spawn_agent("git-agent", "git", "chat123")
        assert try_extract_natural_language_sub_agent("ask nobody-agent to run", "chat123", registry) is None


def test_extract_natural_language_case_insensitive(registry: AgentRegistry) -> None:
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_S()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_S()),
    ):
        registry.spawn_agent("MyAgent", "git", "chat123")
        hit = try_extract_natural_language_sub_agent("tell myagent to ping", "chat123", registry)
        assert hit is not None
        assert hit[0].name == "MyAgent"


def test_extract_natural_language_what_is_doing(registry: AgentRegistry) -> None:
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_S()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_S()),
    ):
        registry.spawn_agent("research_agent", "marketing", "chat123")
        hit = try_extract_natural_language_sub_agent("what is research_agent doing", "chat123", registry)
        assert hit is not None
        assert hit[1] == "status"


def test_route_natural_language_disabled(registry: AgentRegistry, router: AgentRouter) -> None:
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_NLoff()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_NLoff()),
    ):
        registry.spawn_agent("git-agent", "git", "chat123")
        result = router.route("ask git-agent to hello", "chat123", user_id="u1")
        assert result["handled"] is False


def test_resolve_agent_for_dispatch_falls_back_to_owner_scope(
    registry: AgentRegistry,
) -> None:
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_S()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_S()),
    ):
        uid = "tg_9000000001"
        reg = registry
        ag = reg.spawn_agent(
            "scoped-bot",
            "git",
            f"web:{uid}:other-session",
            owner_app_user_id=uid,
        )
        assert ag is not None
        assert (
            resolve_agent_for_dispatch(reg, "scoped-bot", f"web:{uid}:default", None)
            is None
        )
        assert (
            resolve_agent_for_dispatch(reg, "scoped-bot", f"web:{uid}:default", uid)
            is not None
        )


def test_resolve_agent_developer_name_without_agent_suffix(registry: AgentRegistry) -> None:
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_S()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_S()),
    ):
        uid = "tg_9000000003"
        ag = registry.spawn_agent(
            "developer_agent",
            "backend",
            "telegram:99",
            owner_app_user_id=uid,
        )
        assert ag is not None
        linked = resolve_agent_for_dispatch(registry, "developer", "telegram:100", uid)
        assert linked is not None
        assert linked.id == ag.id
        assert linked.parent_chat_id == "telegram:100"


def test_route_mention_uses_global_fallback(registry: AgentRegistry, router: AgentRouter) -> None:
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_S()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_S()),
        patch("app.services.sub_agent_executor.AgentExecutor") as ex_cls,
    ):
        uid = "tg_9000000002"
        reg = registry
        reg.spawn_agent(
            "global-bot",
            "git",
            f"web:{uid}:sess-x",
            owner_app_user_id=uid,
        )
        ex_cls.return_value.execute.return_value = "global_ok"
        out = router.route(
            "@global-bot ping",
            f"web:{uid}:sess-y",
            user_id=uid,
        )
        assert out["handled"] is True
        assert out["response"] == "global_ok"


def test_route_natural_language_ask_to_mock_execute(registry: AgentRegistry, router: AgentRouter) -> None:
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_S()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_S()),
        patch("app.services.sub_agent_executor.AgentExecutor") as ex_cls,
    ):
        registry.spawn_agent("git-agent", "git", "chat123")
        ex_cls.return_value.execute.return_value = "nl_ok"
        result = router.route("ask git-agent to deploy now", "chat123", user_id="u1")
        assert result["handled"] is True
        assert result["response"] == "nl_ok"
        ex_cls.return_value.execute.assert_called_once()


def test_gateway_turn_end_to_end(registry: AgentRegistry) -> None:
    reg = registry
    with (
        patch("app.services.sub_agent_router.get_settings", return_value=_S()),
        patch("app.services.sub_agent_registry.get_settings", return_value=_S()),
    ):
        reg.spawn_agent("git-agent", "git", "web:user-1:default")
        gctx = GatewayContext(user_id="user-1", channel="web", extras={})
        out = try_sub_agent_gateway_turn(gctx, "@git-agent hello", db=None)
        assert out is not None
        assert out["mode"] == "chat"
        assert out["intent"] == "sub_agent_orchestration"
        assert "git" in (out.get("text") or "").lower()
