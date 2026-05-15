# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.gateway.context import GatewayContext
from app.services.inter_agent_coordinator import parse_inter_agent_steps, try_inter_agent_gateway_turn
from app.services.qa_agent.file_analysis import first_path_from_inter_agent_handoff


def test_parse_two_steps_comma_then() -> None:
    steps = parse_inter_agent_steps(
        "ask marketing_agent to draft copy, then ask qa_agent to review for typos"
    )
    assert steps == [
        ("marketing_agent", "draft copy"),
        ("qa_agent", "review for typos"),
    ]


def test_parse_two_steps_sentence_then_ask() -> None:
    steps = parse_inter_agent_steps(
        "Ask marketing_agent to draft social copy. Then ask qa_agent to review for security issues."
    )
    assert steps == [
        ("marketing_agent", "draft social copy"),
        ("qa_agent", "review for security issues"),
    ]


def test_parse_two_steps_sentence_dot_ask_without_then() -> None:
    steps = parse_inter_agent_steps(
        "ask marketing_agent to summarize the release. ask qa_agent to sanity-check the summary"
    )
    assert steps == [
        ("marketing_agent", "summarize the release"),
        ("qa_agent", "sanity-check the summary"),
    ]


def test_first_path_from_handoff() -> None:
    msg = (
        "review the changes\n\n"
        "---\n**Handoff (prior agent output):**\n"
        "Edited `/Users/x/proj/app/main.py` for logging."
    )
    assert first_path_from_inter_agent_handoff(msg) == "/Users/x/proj/app/main.py"


def test_try_inter_agent_gateway_user_id_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    gctx = GatewayContext.from_channel("", "web", {"web_session_id": "sessX"})
    mock_run = MagicMock(return_value="combined")
    monkeypatch.setattr("app.services.inter_agent_coordinator.run_inter_agent_steps", mock_run)
    text = "ask marketing_agent to create a tagline, then ask qa_agent to review it"
    out = try_inter_agent_gateway_turn(gctx, text, None)
    assert out is not None
    assert mock_run.call_args is not None
    assert mock_run.call_args.kwargs["user_id"] == "session:sessX"
