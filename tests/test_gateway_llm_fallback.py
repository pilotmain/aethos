# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Gateway LLM fallback (imperative lines before full chat)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.gateway.context import GatewayContext
from app.services.gateway.llm_fallback import looks_like_unrouted_command, try_gateway_llm_fallback_turn


def test_looks_like_unrouted_command_install() -> None:
    assert looks_like_unrouted_command("install express in the backend folder") is True


def test_looks_like_unrouted_command_question() -> None:
    assert looks_like_unrouted_command("What is express?") is False


def test_looks_like_unrouted_command_how_do_i() -> None:
    assert looks_like_unrouted_command("How do I install express in my project?") is True


def test_try_gateway_llm_fallback_skips_when_llm_off() -> None:
    gctx = GatewayContext(user_id="tg_1", channel="web", extras={})
    with patch("app.services.gateway.llm_fallback.get_settings") as gs:
        gs.return_value = MagicMock(use_real_llm=False, nexa_workspace_root="/tmp/ws")
        assert try_gateway_llm_fallback_turn(gctx, "install lodash", MagicMock()) is None


def test_try_gateway_llm_fallback_returns_payload() -> None:
    gctx = GatewayContext(user_id="tg_1", channel="web", extras={"telegram_user_id": 42})
    db = MagicMock()
    with (
        patch("app.services.gateway.llm_fallback.get_settings") as gs,
        patch(
            "app.services.conversation_context_service.get_or_create_context",
            return_value=MagicMock(),
        ),
        patch("app.services.conversation_context_service.build_context_snapshot", return_value={}),
        patch("app.services.intent_classifier.get_intent", return_value="general_chat"),
        patch(
            "app.services.safe_llm_gateway.safe_llm_text_call",
            return_value="Use **npm install lodash** in your project root.",
        ),
    ):
        gs.return_value = MagicMock(use_real_llm=True, nexa_workspace_root="/tmp/ws")
        out = try_gateway_llm_fallback_turn(gctx, "install lodash in my todo app", db)
    assert out is not None
    assert out.get("mode") == "chat"
    assert out.get("intent") == "llm_fallback_command"
    assert "npm install" in (out.get("text") or "")


def test_try_gateway_llm_fallback_skips_non_general_chat_intent() -> None:
    gctx = GatewayContext(user_id="tg_1", channel="web", extras={})
    db = MagicMock()
    with (
        patch("app.services.gateway.llm_fallback.get_settings") as gs,
        patch(
            "app.services.conversation_context_service.get_or_create_context",
            return_value=MagicMock(),
        ),
        patch("app.services.conversation_context_service.build_context_snapshot", return_value={}),
        patch("app.services.intent_classifier.get_intent", return_value="stuck_dev"),
    ):
        gs.return_value = MagicMock(use_real_llm=True, nexa_workspace_root="/tmp/ws")
        assert try_gateway_llm_fallback_turn(gctx, "docker build fails on CI", db) is None
