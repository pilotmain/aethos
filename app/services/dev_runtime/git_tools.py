"""Thin git helpers built on the allowlisted executor."""

from __future__ import annotations

from pathlib import Path

from app.services.dev_runtime.executor import run_dev_command


def git_status(workspace_root: Path | str) -> dict[str, object]:
    return run_dev_command(workspace_root, "git status")


def git_diff(workspace_root: Path | str) -> dict[str, object]:
    return run_dev_command(workspace_root, "git diff")


def current_branch(workspace_root: Path | str) -> dict[str, object]:
    return run_dev_command(workspace_root, "git branch")


__all__ = ["git_status", "git_diff", "current_branch"]
