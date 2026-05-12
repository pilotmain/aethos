# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Host executor visibility helpers (copy + truncation only)."""

from __future__ import annotations

from unittest.mock import patch

from app.services.host_executor_visibility import (
    format_host_completion_message,
    format_host_confirmation,
    host_executor_panel_public,
    telegram_host_command_text,
    truncate_output_lines,
)


def test_confirmation_includes_approval_and_host_action() -> None:
    text = format_host_confirmation(
        {"host_action": "run_command", "run_name": "pytest"},
        "Run tests (pytest)",
    )
    assert "Approval: required" in text
    assert "host_action:" in text
    assert "Reply" in text and "run" in text.lower()


def test_completion_truncates_long_output() -> None:
    long_out = "\n".join(f"line {i}" for i in range(50))
    msg = format_host_completion_message(
        job_id=99,
        title="T",
        success=True,
        body=long_out,
        err=None,
    )
    assert "Job #99" in msg
    assert "Result: success" in msg
    assert msg.count("line") < 50


def test_truncate_output_lines() -> None:
    t = truncate_output_lines("a\nb\nc\n" * 20, max_lines=3, max_chars=500)
    assert "…" in t or len(t.splitlines()) <= 4


def test_panel_public_has_expected_keys() -> None:
    with patch("app.services.host_executor_visibility.get_settings") as m:
        m.return_value = type(
            "S",
            (),
            {
                "nexa_host_executor_enabled": True,
                "host_executor_work_root": "",
                "host_executor_timeout_seconds": 60,
                "host_executor_max_file_bytes": 1024,
            },
        )()
        p = host_executor_panel_public()
    assert "enabled" in p and "work_root" in p
    assert "git_status" in p["allowed_host_actions"]
    assert "pytest" in p["allowed_run_names"]


def test_telegram_host_text_when_disabled() -> None:
    with patch("app.services.host_executor_visibility.get_settings") as m:
        m.return_value = type(
            "S",
            (),
            {
                "nexa_host_executor_enabled": False,
                "host_executor_work_root": "",
                "host_executor_timeout_seconds": 120,
                "host_executor_max_file_bytes": 262_144,
            },
        )()
        t = telegram_host_command_text()
    assert "disabled" in t.lower() or "NEXA_HOST_EXECUTOR" in t
