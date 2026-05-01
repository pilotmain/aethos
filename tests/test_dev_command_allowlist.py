"""Phase 23 — allowlisted dev commands."""

from __future__ import annotations

import subprocess

from app.services.dev_runtime.executor import allowed_commands, run_dev_command


def test_git_status_allowed(tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    out = run_dev_command(repo, "git status")
    assert out.get("ok") is True
    assert "stdout" in out


def test_rm_rf_blocked(tmp_path) -> None:
    repo = tmp_path / "r2"
    repo.mkdir()
    out = run_dev_command(repo, "rm -rf /")
    assert out.get("ok") is False
    assert out.get("error") == "command_not_allowlisted"


def test_allowlist_contains_git_status() -> None:
    assert "git status" in allowed_commands()
