"""Co-pilot heuristics: goal/trivial detection and next-step appends."""

from __future__ import annotations

from app.services.copilot_next_steps import (
    format_next_steps_block,
    is_goal_oriented_user_message,
    is_trivial_user_message,
    should_append_next_steps,
)
from app.services.response_composer import (
    CLARIFY_PROMPT,
    ASSIST_PROMPT,
    validate_composed_response,
)


def test_trivial_messages() -> None:
    assert is_trivial_user_message("ok")
    assert is_trivial_user_message("thanks")
    assert is_trivial_user_message("  Thanks!  ")
    assert not is_trivial_user_message("help me launch this product next week")


def test_goal_oriented_heuristic() -> None:
    assert is_goal_oriented_user_message("I want to launch this product in Q2 and need a plan")
    assert is_goal_oriented_user_message("@marketing analyze pilotmain.com for positioning")
    assert not is_goal_oriented_user_message("no")


def test_format_next_steps_block() -> None:
    s = format_next_steps_block(["Create a one-pager", "Run /doc create pdf after"])
    assert s.startswith("Next steps:\n")
    assert "- Create a one-pager" in s


def test_should_append_respects_trivial() -> None:
    assert not should_append_next_steps(
        "clarify",
        "ok",
        ["@marketing check https://x.com"],
    )
    assert should_append_next_steps(
        "clarify",
        "help me market my site",
        ["@marketing …", "x"],
    )
    assert not should_append_next_steps("nudge", "help", ["a", "b"])


def test_validate_composed_accepts_next_steps() -> None:
    v = validate_composed_response(
        {
            "message": "Here is the answer.",
            "should_ask_followup": False,
            "followup_question": None,
            "suggested_microstep": None,
            "next_steps": ["@marketing analyze example.com", "x", "y", "z", "drop"],
        }
    )
    assert v is not None
    assert v["next_steps"] is not None
    assert len(v["next_steps"] or []) == 4  # cap


def test_clarify_prompt_co_pilot_and_nexa_actions() -> None:
    assert "next_steps" in CLARIFY_PROMPT
    assert "/doc" in CLARIFY_PROMPT
    assert "Insight" in CLARIFY_PROMPT or "insight" in CLARIFY_PROMPT.lower()


def test_assist_prompt_thread_and_insight() -> None:
    assert "next_steps" in ASSIST_PROMPT
    assert "ongoing topic" in ASSIST_PROMPT.lower() or "thread" in ASSIST_PROMPT.lower()
