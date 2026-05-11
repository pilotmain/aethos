"""Regression: command timeouts must honor env and long scaffold steps."""

from __future__ import annotations

from unittest.mock import patch

from app.services import host_executor


def test_command_timeout_uses_max_of_env_and_caller_hint() -> None:
    class S:
        nexa_command_timeout_seconds = 600

    with patch.object(host_executor, "_host_settings", return_value=S()):
        assert host_executor._command_timeout(60) == 600


def test_command_timeout_uses_max_when_env_lower_than_hint() -> None:
    class S:
        nexa_command_timeout_seconds = 60

    with patch.object(host_executor, "_host_settings", return_value=S()):
        assert host_executor._command_timeout(120) == 120


def test_create_react_app_argv_gets_task_floor() -> None:
    class S:
        nexa_command_timeout_seconds = 60
        nexa_task_timeout_seconds = 300

    with patch.object(host_executor, "_host_settings", return_value=S()):
        base = host_executor._command_timeout(60)
        t = host_executor._apply_task_scaffold_timeout(["npx", "--yes", "create-react-app", "x"], base)
        assert t >= 300
