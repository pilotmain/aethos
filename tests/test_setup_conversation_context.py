# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_conversation_context import SetupConversationContext, get_setup_conversation


def test_routing_continuity_hybrid() -> None:
    ctx = SetupConversationContext()
    ctx.record("routing_mode", "hybrid")
    line = ctx.explain_routing(mode="hybrid", preference="balanced")
    assert "Hybrid" in line or "hybrid" in line.lower()
    assert "local" in line.lower()


def test_get_setup_conversation_singleton() -> None:
    assert get_setup_conversation() is get_setup_conversation()
