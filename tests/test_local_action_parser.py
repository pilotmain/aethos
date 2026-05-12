# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.local_action_parser import (
    is_dev_command,
    parse_local_action,
)
from app.services.dev_task_service import (
    build_cursor_instruction,
    extract_cursor_request,
    is_cursor_request,
)


def test_is_dev_command() -> None:
    assert is_dev_command("  /dev run-tests  ") is True
    assert is_dev_command("/improve x") is False


def test_parse_create_cursor_task() -> None:
    p = parse_local_action(
        "/dev create-cursor-task improve nudge responses so they feel less repetitive"
    )
    assert p["command_type"] == "create-cursor-task"
    assert "nudge" in p["instruction"]


def test_parse_run_tests() -> None:
    p = parse_local_action(" /dev run-tests ")
    assert p["command_type"] == "run-tests"
    assert p["instruction"] == ""


def test_unsupported_falls_through_intent() -> None:
    import pytest

    with pytest.raises(ValueError) as e:
        parse_local_action("/dev not-a-real-command")
    assert "Unsupported command" in str(e.value)


def test_cursor_request_detected() -> None:
    assert is_cursor_request("please tell cursor to fix memory cleanup") is True
    assert extract_cursor_request("make a cursor task for refactor the planner") == "refactor the planner"


def test_ask_cursor_without_to_still_queues_dev_job() -> None:
    """User phrasing is often "ask cursor what X" not "ask cursor to ..."."""
    t = "Ask  cursor what feature on the Nexa project can we add?"
    assert is_cursor_request(t) is True
    assert "what feature" in (extract_cursor_request(t) or "")


def test_cursor_request_strips_work_prefix() -> None:
    instruction, needs_more_detail = build_cursor_instruction(
        "please tell cursor to work on the follow-up scheduler"
    )
    assert needs_more_detail is False
    assert instruction == "the follow-up scheduler"


def test_cursor_request_uses_reply_context_when_vague() -> None:
    instruction, needs_more_detail = build_cursor_instruction(
        "tell cursor to work on this",
        replied_text="The memory forget flow should cancel reminders too.",
    )
    assert needs_more_detail is False
    assert "Context from replied message" in instruction
    assert "cancel reminders" in instruction


def test_cursor_request_asks_for_more_detail_when_vague_and_no_reply() -> None:
    instruction, needs_more_detail = build_cursor_instruction("tell cursor to work on this")
    assert instruction == "work on this"
    assert needs_more_detail is True
