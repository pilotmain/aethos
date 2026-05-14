# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.inter_agent_coordinator import parse_inter_agent_steps
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
