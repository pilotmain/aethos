# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Tests for Agentic OS gateway helpers (status NL, inter-agent parse, visibility feed)."""

from __future__ import annotations

from app.services.agent_visibility_feed import (
    clear_visibility_feed_for_tests,
    drain_user_visibility_banner,
    push_agent_spawn_notice,
)
from app.services.host_executor_intent import parse_status_intent
from app.services.inter_agent_coordinator import parse_inter_agent_steps


def teardown_module() -> None:
    clear_visibility_feed_for_tests()


def test_parse_status_intent() -> None:
    assert parse_status_intent("what's the status") == {"intent": "get_status"}
    assert parse_status_intent("show my tasks") == {"intent": "list_tasks"}
    assert parse_status_intent("heartbeat") == {"intent": "heartbeat"}
    assert parse_status_intent("run ls") is None


def test_parse_inter_agent_steps_multi() -> None:
    steps = parse_inter_agent_steps(
        "ask marketing_agent to write a tagline and ask qa_agent to review it"
    )
    assert steps is not None
    assert len(steps) == 2
    assert steps[0][0] == "marketing_agent"
    assert steps[1][0] == "qa_agent"


def test_parse_inter_agent_steps_single() -> None:
    steps = parse_inter_agent_steps("tell qa_agent to run tests")
    assert steps == [("qa_agent", "run tests")]


def test_visibility_feed_roundtrip() -> None:
    clear_visibility_feed_for_tests()
    push_agent_spawn_notice("web_u1", agent_name="foo_agent", domain="qa", agent_id="abc12345")
    banner = drain_user_visibility_banner("web_u1")
    assert banner is not None
    assert "foo_agent" in banner
    assert drain_user_visibility_banner("web_u1") is None
