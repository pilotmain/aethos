"""Unit tests for execution/assignment reply sanitization (hallucination guard)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.services.response_sanitizer import (
    dev_execution_available,
    reply_claims_assignment_without_evidence,
    sanitize_execution_and_assignment_reply,
    user_asks_dev_code,
)


def test_reply_claims_assignment_detects_assigned_to_handle() -> None:
    assert reply_claims_assignment_without_evidence("I've assigned @dev to fix it.")
    assert not reply_claims_assignment_without_evidence(
        "assignment # 42 is ready for review."
    )


def test_user_asks_dev_code_requires_dev_and_code_intent() -> None:
    assert user_asks_dev_code("@dev please implement the API fix")
    assert not user_asks_dev_code("talk to @dev about priorities")
    assert not user_asks_dev_code("implement the API fix")


@patch("app.services.response_sanitizer.get_settings")
def test_sanitize_skips_when_related_job_ids(mock_gs) -> None:
    mock_gs.return_value = SimpleNamespace(
        nexa_host_executor_enabled=False,
        cursor_enabled=False,
    )
    body = "I've assigned @dev — they're on it."
    out = sanitize_execution_and_assignment_reply(
        body,
        user_text="@orchestrator assign @dev",
        related_job_ids=[1],
    )
    assert out == body


@patch("app.services.response_sanitizer.get_settings")
def test_sanitize_skips_when_permission_pending(mock_gs) -> None:
    mock_gs.return_value = SimpleNamespace(
        nexa_host_executor_enabled=False,
        cursor_enabled=False,
    )
    body = "I've assigned @dev."
    out = sanitize_execution_and_assignment_reply(
        body,
        user_text="@orchestrator",
        permission_required={"kind": "host"},
    )
    assert out == body


@patch("app.services.response_sanitizer.get_settings")
def test_sanitize_appends_tracking_note_when_no_ids(mock_gs) -> None:
    mock_gs.return_value = SimpleNamespace(
        nexa_host_executor_enabled=True,
        cursor_enabled=False,
    )
    body = "I've assigned @dev to handle the migration."
    out = sanitize_execution_and_assignment_reply(
        body,
        user_text="@orchestrator please route this",
    )
    assert body in out
    assert "tracked assignment id" in out.lower()


@patch("app.services.response_sanitizer.get_settings")
def test_sanitize_replaces_fake_async_when_tracked_expected(mock_gs) -> None:
    mock_gs.return_value = SimpleNamespace(
        nexa_host_executor_enabled=True,
        cursor_enabled=False,
    )
    out = sanitize_execution_and_assignment_reply(
        "I'm working on it.",
        user_text="@orchestrator track this",
    )
    assert "assignment id" in out.lower()
    assert "i'm working on it" not in out.lower()


@patch("app.services.response_sanitizer.get_settings")
def test_sanitize_dev_disabled_lead_for_code_request(mock_gs) -> None:
    mock_gs.return_value = SimpleNamespace(
        nexa_host_executor_enabled=False,
        cursor_enabled=False,
    )
    out = sanitize_execution_and_assignment_reply(
        "Consider using REST with JWT for your API.",
        user_text="@dev build the login API",
    )
    assert "dev execution is not enabled" in out.lower()


@patch("app.services.response_sanitizer.get_settings")
def test_sanitize_appends_dev_disabled_when_execution_off(mock_gs) -> None:
    mock_gs.return_value = SimpleNamespace(
        nexa_host_executor_enabled=False,
        cursor_enabled=False,
    )
    body = "@dev is implementing the patch now."
    out = sanitize_execution_and_assignment_reply(
        body,
        user_text="@dev fix the bug in the API",
    )
    assert body in out
    assert "enabled here" in out.lower()


@patch("app.services.response_sanitizer.get_settings")
def test_dev_execution_available_or_cursor(mock_gs) -> None:
    mock_gs.return_value = SimpleNamespace(
        nexa_host_executor_enabled=False,
        cursor_enabled=True,
    )
    assert dev_execution_available()


@patch("app.services.response_sanitizer.get_settings")
def test_sanitize_strips_fake_sessions_spawn_when_no_spawn_id(mock_gs) -> None:
    mock_gs.return_value = SimpleNamespace(
        nexa_host_executor_enabled=True,
        cursor_enabled=False,
    )
    body = "Invoking sessions_spawn.\nAwaiting backend confirmation."
    out = sanitize_execution_and_assignment_reply(
        body,
        user_text="@boss spawn sessions with @research-analyst and @qa",
    )
    assert "Awaiting backend confirmation" not in out
    assert "simulated" in out.lower()


@patch("app.services.response_sanitizer.get_settings")
def test_sanitize_keeps_reply_when_spawn_id_present(mock_gs) -> None:
    mock_gs.return_value = SimpleNamespace(
        nexa_host_executor_enabled=True,
        cursor_enabled=False,
    )
    body = "Spawn group created spawn_abcd1234567890 assignments #1 #2"
    out = sanitize_execution_and_assignment_reply(
        body,
        user_text="@boss create swarm with @a and @b",
    )
    assert out == body
