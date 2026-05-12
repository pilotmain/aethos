# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""General question detection, correction strip, and answer service."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.agent_orchestrator import handle_research_agent_request
from app.services.general_answer_service import (
    answer_general_question,
    fallback_general_answer,
)
from app.services.general_response import (
    is_simple_greeting,
    looks_like_general_question,
    strip_correction_prefix,
)


def test_looks_like_general_question() -> None:
    assert looks_like_general_question("What is MCP?") is True
    assert looks_like_general_question("Give me an update on Ethiopian economy") is True
    assert looks_like_general_question("Explain how DNS works") is True


def test_strip_correction_prefix() -> None:
    assert "Ethiopian" in strip_correction_prefix("No, I asked about Ethiopian economy")
    assert strip_correction_prefix("hello") == "hello"


def test_fallback_not_empty() -> None:
    assert "LLM" in fallback_general_answer("x") or "connection" in fallback_general_answer("x")


@patch("app.services.general_answer_service.safe_llm_text_call", return_value="MCP is the protocol.")
def test_answer_general_question_uses_llm(_mock) -> None:
    out = answer_general_question("What is MCP?", conversation_snapshot=None)
    assert "MCP" in out


@patch("app.services.general_answer_service.safe_llm_text_call", side_effect=RuntimeError("no api"))
def test_answer_falls_back_when_llm_fails(_mock) -> None:
    out = answer_general_question("What is X?", conversation_snapshot={})
    assert "connection" in out.lower() or "detail" in out.lower()


@patch("app.services.web_research_intent.app_user_allows_internal_fetch", return_value=False)
@patch("app.services.web_research_intent.extract_urls_from_text", return_value=[])
@patch("app.services.general_answer_service.safe_llm_text_call", return_value="Research body")
def test_research_agent_uses_general_answer(_m1, _m2, _llm) -> None:
    db = MagicMock()
    out = handle_research_agent_request(
        db,
        "u1",
        "Ethiopian economy update",
        conversation_snapshot={"active_topic": "x"},
    )
    assert "Research" in out
    assert "Research body" in out


def test_hello_still_greeting_not_general_question_path() -> None:
    assert is_simple_greeting("hi") is True
    # greetings are not "general question" in the narrow sense, but "hi?" would have ?
    assert looks_like_general_question("hi") is False
