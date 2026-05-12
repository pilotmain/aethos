# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Research / web capability user-facing copy (no secrets)."""

from __future__ import annotations

from unittest.mock import patch

from app.services import research_capability_copy as rcc


def test_is_research_capability_question() -> None:
    assert rcc.is_research_capability_question("Do you have access to web research or Google?")
    assert rcc.is_research_capability_question("can you search the web for this")
    assert not rcc.is_research_capability_question("/help what commands are there")
    assert not rcc.is_research_capability_question("list commands")


@patch("app.services.research_capability_copy.get_settings")
def test_research_message_when_search_disabled_public_enabled(mock_gs) -> None:
    m = type(
        "S",
        (),
        {
            "nexa_web_access_enabled": True,
            "nexa_web_search_enabled": False,
            "nexa_web_search_provider": "none",
            "nexa_web_search_api_key": "",
            "nexa_browser_preview_enabled": False,
        },
    )()
    mock_gs.return_value = m
    out = rcc.format_research_capability_message()
    assert "public" in out.lower() or "Public" in out
    assert "disabled" in out.lower() and "web search" in out.lower()
    assert "paste" in out.lower() or "https" in out.lower()


@patch("app.services.research_capability_copy.get_settings")
def test_research_message_when_search_enabled_brave(mock_gs) -> None:
    m = type(
        "S",
        (),
        {
            "nexa_web_access_enabled": True,
            "nexa_web_search_enabled": True,
            "nexa_web_search_provider": "brave",
            "nexa_web_search_api_key": "test-key-not-real",
            "nexa_browser_preview_enabled": False,
        },
    )()
    mock_gs.return_value = m
    out = rcc.format_research_capability_message()
    assert "brave" in out.lower()
    assert "enabled" in out.lower()


def test_compose_clarify_uses_research_copy_when_use_real_llm() -> None:
    from app.services.response_composer import (
        ResponseContext,
        compose_clarify_response,
    )

    s = type(
        "S",
        (),
        {
            "nexa_web_access_enabled": True,
            "nexa_web_search_enabled": False,
            "nexa_web_search_provider": "none",
            "nexa_web_search_api_key": "",
            "nexa_browser_preview_enabled": False,
        },
    )()
    with patch("app.services.research_capability_copy.get_settings", return_value=s), patch(
        "app.services.response_composer._invoke_llm"
    ) as mock_llm:
        mock_llm.side_effect = AssertionError("should not call LLM for research capability question")
        ctx = ResponseContext(
            user_message="Do you have access to web research or Google?",
            intent="capability_question",
            behavior="clarify",
            has_active_plan=False,
            focus_task=None,
            selected_tasks=[],
            deferred_lines=[],
            planning_style="gentle",
            detected_state=None,
        )
        res = compose_clarify_response(ctx)
    assert "Research capability" in res["message"] or "research" in res["message"].lower()
    assert mock_llm.call_count == 0


def test_handle_message_capability_uses_research_for_telegram_path() -> None:
    from app.services.legacy_behavior_utils import Context, handle_message

    s = type(
        "S",
        (),
        {
            "nexa_web_access_enabled": True,
            "nexa_web_search_enabled": False,
            "nexa_web_search_provider": "none",
            "nexa_web_search_api_key": "",
            "nexa_browser_preview_enabled": False,
        },
    )()
    with patch("app.services.research_capability_copy.get_settings", return_value=s):
        ctx = Context("u1", tasks=[], last_plan=[], memory={})
        out = handle_message(
            "Do you have access to web research?",
            "capability_question",
            ctx,
        )
    assert "Research capability" in out or "public" in out.lower()


# Ensure fallback path when LLM is off
def test_fallback_capability_response() -> None:
    from app.services.response_composer import fallback_capability_response

    with patch("app.services.research_capability_copy.get_settings") as mock_gs:
        mock_gs.return_value = type(
            "S",
            (),
            {
                "nexa_web_access_enabled": True,
                "nexa_web_search_enabled": False,
                "nexa_web_search_provider": "none",
                "nexa_web_search_api_key": "",
                "nexa_browser_preview_enabled": False,
            },
        )()
        t = fallback_capability_response("search the web for this — can you?")
    assert "Research capability" in t or "public" in t.lower()
