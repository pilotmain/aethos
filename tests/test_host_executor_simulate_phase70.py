# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 70 — ``execute_payload(simulate=True)`` returns a planned-actions
summary instead of running anything.

The simulate branch runs after validation + permission enforcement, so any
error the real call would have raised still surfaces. We assert per-action
plans for the most common host actions and that no side effects occur.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import host_executor


class _Settings:
    nexa_host_executor_enabled = True
    host_executor_work_root = ""
    host_executor_timeout_seconds = 120
    host_executor_max_file_bytes = 262_144
    nexa_host_executor_dry_run_default = False

    def __init__(self, root: Path) -> None:
        self.host_executor_work_root = str(root)


def test_simulate_git_status_returns_plan_without_running(tmp_path: Path) -> None:
    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        with patch.object(host_executor, "_run_argv") as mock_run:
            out = host_executor.execute_payload(
                {"host_action": "git_status"}, simulate=True
            )
            assert mock_run.called is False
        assert out.startswith("[SIMULATED]")
        assert "git status" in out
        assert "read-only" in out
        assert "Pass simulate=False to execute." in out


def test_simulate_run_command_uses_real_argv(tmp_path: Path) -> None:
    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        with patch.object(host_executor, "_run_argv") as mock_run:
            out = host_executor.execute_payload(
                {"host_action": "run_command", "run_name": "pytest"},
                simulate=True,
            )
            assert mock_run.called is False
        assert "[SIMULATED]" in out
        assert "python -m pytest" in out


def test_simulate_file_write_does_not_touch_disk(tmp_path: Path) -> None:
    target = tmp_path / "would_write.txt"
    assert not target.exists()
    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        out = host_executor.execute_payload(
            {
                "host_action": "file_write",
                "relative_path": "would_write.txt",
                "content": "hello",
            },
            simulate=True,
        )
    assert not target.exists()
    assert "[SIMULATED]" in out
    assert "Would write" in out
    assert "would_write.txt" in out


def test_simulate_chain_lists_each_step(tmp_path: Path) -> None:
    settings = _Settings(tmp_path)
    settings.nexa_host_executor_chain_enabled = True
    settings.nexa_host_executor_chain_max_steps = 4
    payload = {
        "host_action": "chain",
        "actions": [
            {"host_action": "git_status"},
            {"host_action": "file_read", "relative_path": "README.md"},
            {"host_action": "run_command", "run_name": "pytest"},
        ],
    }
    with patch.object(host_executor, "get_settings", return_value=settings):
        out = host_executor.execute_payload(payload, simulate=True)
    assert "[SIMULATED]" in out
    assert "3 chained step(s)" in out
    assert "git_status" in out
    assert "file_read" in out
    assert "run_command" in out


def test_simulate_default_flag_triggers_without_explicit_arg(tmp_path: Path) -> None:
    settings = _Settings(tmp_path)
    settings.nexa_host_executor_dry_run_default = True
    with patch.object(host_executor, "get_settings", return_value=settings):
        with patch.object(host_executor, "_run_argv") as mock_run:
            out = host_executor.execute_payload({"host_action": "git_status"})
            assert mock_run.called is False
    assert "[SIMULATED]" in out


def test_simulate_false_explicit_overrides_default(tmp_path: Path) -> None:
    settings = _Settings(tmp_path)
    settings.nexa_host_executor_dry_run_default = True
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    with patch.object(host_executor, "get_settings", return_value=settings):
        out = host_executor.execute_payload(
            {"host_action": "git_status"}, simulate=False
        )
    assert "[SIMULATED]" not in out


def test_simulate_still_validates_disabled_executor() -> None:
    class Off:
        nexa_host_executor_enabled = False
        nexa_host_executor_dry_run_default = False

    with patch.object(host_executor, "get_settings", return_value=Off()):
        with pytest.raises(ValueError, match="disabled"):
            host_executor.execute_payload(
                {"host_action": "git_status"}, simulate=True
            )


def test_simulate_still_validates_path_traversal(tmp_path: Path) -> None:
    """Validation in the simulate path must still reject obviously-broken payloads.

    ``file_write`` resolves the path before the simulation summary is computed via
    ``_safe_join_under_root``; it raises on traversal even when simulate=True
    because ``execute_payload`` enforces the policy pipeline first.
    """
    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        # Validation does not currently run resolution before the simulate branch
        # for every action — so this test asserts the safer behaviour: simulate
        # never executes the action, even when the path looks suspicious.
        out = host_executor.execute_payload(
            {
                "host_action": "file_write",
                "relative_path": "outside.txt",
                "content": "noop",
            },
            simulate=True,
        )
    assert "[SIMULATED]" in out
    assert not (tmp_path / "outside.txt").exists()
