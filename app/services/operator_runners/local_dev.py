# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Local workspace git snapshot (read-only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.services.dev_runtime.executor import run_dev_command
from app.services.dev_runtime.workspace import list_workspaces
from app.services.operator_runners.base import evidence_shell, format_operator_progress


def run_git_status_at_path(repo_path: str) -> tuple[str, dict[str, Any], list[str], bool]:
    """Run allowlisted git status under an explicit absolute path (e.g. from ``Workspace:`` line)."""
    progress = ["Inspecting workspace path from message", "Running git status"]
    root = Path(repo_path).expanduser().resolve()
    if not root.is_dir():
        body = (
            format_operator_progress(progress + ["Stopped: workspace path not found"])
            + f"\n\n---\n\n`{repo_path}` is not a directory on this host."
        )
        return body, evidence_shell(provider="local_dev", commands=[], workspace_path=str(repo_path)), progress, False

    res = run_dev_command(root, "git status --porcelain")
    if res.get("error") == "command_not_allowlisted":
        res = run_dev_command(root, "git status")
    ok = bool(res.get("ok"))
    cmds = [{"command": res.get("command") or "git status", "result": res}]
    ev = evidence_shell(provider="local_dev", commands=cmds, workspace_path=str(root))
    out = (res.get("stdout") or res.get("stderr") or str(res.get("error") or "")).strip()
    lines = [
        format_operator_progress(progress),
        "",
        "---",
        "",
        f"`git status` in `{root}`",
        "",
        "```",
        out[:8000] if out else "(empty)",
        "```",
    ]
    return "\n".join(lines), ev, progress, ok


def run_local_git_status(db: Session, user_id: str) -> tuple[str, dict[str, Any], list[str], bool]:
    rows = list_workspaces(db, user_id)
    progress = ["Inspecting registered workspace", "Running git status"]
    if not rows:
        body = (
            format_operator_progress(progress + ["Stopped: no dev workspace registered"])
            + "\n\n---\n\nRegister a repo path under Mission Control → Dev / workspace."
        )
        return body, evidence_shell(provider="local_dev", commands=[], workspace_path=None), progress, False

    ws = rows[0]
    path = str(getattr(ws, "repo_path", "") or "").strip()
    if not path:
        txt = format_operator_progress(progress + ["Stopped: workspace path empty"]) + "\n\n---\n\n"
        return txt, evidence_shell(provider="local_dev", commands=[], workspace_path=None), progress, False

    res = run_dev_command(Path(path), "git status --porcelain")
    if res.get("error") == "command_not_allowlisted":
        res = run_dev_command(Path(path), "git status")
    ok = bool(res.get("ok"))
    cmds = [{"command": res.get("command") or "git status", "result": res}]
    ev = evidence_shell(provider="local_dev", commands=cmds, workspace_path=path)
    out = (res.get("stdout") or res.get("stderr") or str(res.get("error") or "")).strip()
    lines = [
        format_operator_progress(progress),
        "",
        "---",
        "",
        f"`git status` in `{path}`",
        "",
        "```",
        out[:8000] if out else "(empty)",
        "```",
    ]
    body = "\n".join(lines)
    return body, ev, progress, ok
