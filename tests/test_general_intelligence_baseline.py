"""Greeting path, weak-input skips, ops status routing, and worktree copy."""

import re
from unittest.mock import MagicMock, patch

import pytest

from app.services.dev_worktree_guards import ensure_clean_worktree
from app.services.general_response import (
    detect_greeting_type,
    is_simple_greeting,
    should_skip_weak_input_for_substantive_message,
    simple_greeting_reply,
)
from app.services.intent_classifier import is_command_question
from app.services.ops_handler import handle_nexa_ops_mention
from app.services.ops_router import parse_ops_command
from app.services.telegram_onboarding import is_weak_input


def test_hello_simple_greeting() -> None:
    assert is_simple_greeting("hi") is True
    assert is_simple_greeting("Hello, can you say hello back") is True


def test_detect_greeting_type_time_of_day_and_hi() -> None:
    assert detect_greeting_type("Good morning") == "morning"
    assert detect_greeting_type("GOOD MORNING") == "morning"
    assert detect_greeting_type("Good afternoon!") == "afternoon"
    assert detect_greeting_type("hi") == "hi"
    assert detect_greeting_type("yo") == "default"


def test_simple_greeting_reply_pools_and_hint(monkeypatch) -> None:
    monkeypatch.setattr("random.choice", lambda seq: seq[0])
    g = simple_greeting_reply("Good morning")
    assert "Good morning" in g or "Morning" in g
    assert "You can talk normally" in g
    assert "@dev" in g
    g2 = simple_greeting_reply("hi")
    assert g2.startswith("Hi — I") and "here" in g2  # first option in "hi" pool


def test_hello_back_does_not_trigger_onboarding_path_via_weak() -> None:
    """'Hello, can you say hello back' is not weak / vague-only input."""
    assert is_weak_input("Hello, can you say hello back") is False
    assert should_skip_weak_input_for_substantive_message("Hello, can you say hello back") is True


def test_direct_question_not_weak() -> None:
    assert is_weak_input("What is 2+2?") is False
    assert should_skip_weak_input_for_substantive_message("What is 2+2?") is True


def test_what_are_commands() -> None:
    assert is_command_question("What are the commands you understand?") is True
    assert is_weak_input("What are the commands you understand?") is False


def test_ops_status_parsing_variants() -> None:
    r = parse_ops_command("status", known_project_keys=["nexa"])
    assert r["action"] == "status"
    r2 = parse_ops_command("status nexa", known_project_keys=["nexa"])
    assert r2["action"] == "status"
    assert (r2.get("payload") or {}).get("project_key") == "nexa"
    r3 = parse_ops_command("nexa status", known_project_keys=["nexa"])
    assert r3["action"] == "status"
    assert (r3.get("payload") or {}).get("project_key") == "nexa"


def test_ops_unknown_suggestion(monkeypatch) -> None:
    def _no_legacy(*_a, **_k):
        return None

    monkeypatch.setattr("app.services.ops_mention_routing.ops_mention_reply", _no_legacy)
    monkeypatch.setattr("app.services.project_registry.list_project_keys", lambda _db: [])
    monkeypatch.setattr("app.services.project_registry.get_default_project", lambda _db: None)

    out = handle_nexa_ops_mention(
        MagicMock(),
        "u1",
        "frobulate the matrix completely",
        telegram_chat_id=None,
        cctx=None,
        list_jobs=lambda *a, **k: [],
        format_job_row_short=lambda j: "x",
    )
    assert "didn’t understand" in out
    assert "status" in out.lower()
    assert "@ops" in out or "`@ops" in out


@patch("app.services.dev_worktree_guards.subprocess.run")
def test_dirty_worktree_message_content(mock_run) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout=" M foo.txt\n")
    with pytest.raises(RuntimeError) as ei:
        ensure_clean_worktree("/tmp")
    msg = str(ei.value)
    assert "Dev Agent paused" in msg
    assert re.search(r"git\s+status", msg)
    assert "uncommitted" in msg


def test_brain_dump_still_allows_list_not_greeting() -> None:
    assert is_simple_greeting("I need to finish report, call mom, clean room") is False
