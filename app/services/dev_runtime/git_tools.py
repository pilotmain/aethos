"""Git helpers — allowlisted reads + privileged commits when explicitly authorized."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from app.models.dev_runtime import NexaDevWorkspace
from app.services.dev_runtime.executor import run_dev_command
from app.services.dev_runtime.workspace import validate_workspace_path


def git_status(workspace_root: Path | str) -> dict[str, object]:
    return run_dev_command(workspace_root, "git status")


def git_diff(workspace_root: Path | str) -> dict[str, object]:
    return run_dev_command(workspace_root, "git diff")


def current_branch(workspace_root: Path | str) -> dict[str, object]:
    return run_dev_command(workspace_root, "git branch")


def changed_files(workspace_root: Path | str) -> list[str]:
    """Return a best-effort list of paths from ``git status --porcelain``."""
    root = validate_workspace_path(str(workspace_root))
    r = run_dev_command(root, "git status --porcelain")
    if not r.get("ok"):
        return []
    out: list[str] = []
    for line in str(r.get("stdout") or "").splitlines():
        line = line.rstrip("\n")
        if len(line) > 3 and line[2] == " ":
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ")[-1].strip()
            if path:
                out.append(path)
    return sorted(set(out))


def create_commit(workspace_root: Path | str, message: str, *, allow_commit: bool) -> dict[str, Any]:
    """
    Stage all changes and commit. Uses direct ``git`` invocation (not the allowlisted
    one-string runner) because commit messages are dynamic — only call when
    ``allow_commit`` was explicitly granted by the dev mission API.
    """
    if not allow_commit:
        return {"ok": False, "error": "commit_not_allowed"}
    root = validate_workspace_path(str(workspace_root))
    msg = (message or "").strip()[:500]
    if not msg:
        return {"ok": False, "error": "empty_commit_message"}
    timeout = 120.0
    try:
        add = subprocess.run(
            ["git", "add", "-A"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if add.returncode != 0:
            return {
                "ok": False,
                "error": "git_add_failed",
                "stderr": (add.stderr or "")[-4000:],
            }
        commit = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": commit.returncode == 0,
            "returncode": commit.returncode,
            "stdout": (commit.stdout or "")[-8000:],
            "stderr": (commit.stderr or "")[-8000:],
        }
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"ok": False, "error": str(exc)[:2000]}


def get_diff_summary(repo_path: Path | str) -> dict[str, Any]:
    """
    Summarize uncommitted changes for coding-agent context (no raw secrets guaranteed —
    callers still gate before external providers).
    """
    root = validate_workspace_path(str(repo_path))
    gd = git_diff(root)
    stdout = str(gd.get("stdout") or "")
    ufs = changed_files(root)
    return {
        "changed_files": ufs,
        "changed_file_count": len(ufs),
        "diff_chars": len(stdout),
        "diff_line_count": stdout.count("\n") + (1 if stdout.strip() else 0),
        "has_uncommitted": bool(ufs or stdout.strip()),
        "diff_preview": stdout[:8000],
    }


def prepare_pr_summary(workspace: NexaDevWorkspace, run_result: dict[str, Any] | None) -> dict[str, Any]:
    """Merge workspace context with PR summary text for UI / export."""
    from app.services.dev_runtime.pr import prepare_pr_summary as _title_body

    goal = (run_result or {}).get("goal") or ""
    base = _title_body(goal, run_result)
    base["workspace_id"] = workspace.id
    base["repo_path"] = workspace.repo_path
    base["adapter_used"] = (run_result or {}).get("adapter_used")
    return base


__all__ = [
    "git_status",
    "git_diff",
    "current_branch",
    "changed_files",
    "create_commit",
    "get_diff_summary",
    "prepare_pr_summary",
]
