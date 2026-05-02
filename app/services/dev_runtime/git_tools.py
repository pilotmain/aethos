"""Git helpers — allowlisted reads + privileged commits when explicitly authorized."""

from __future__ import annotations

import re
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


def rev_parse_head(workspace_root: Path | str) -> str | None:
    """Return current ``HEAD`` commit hash or ``None``."""
    root = validate_workspace_path(str(workspace_root))
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=60.0,
        )
        if r.returncode != 0:
            return None
        h = (r.stdout or "").strip()
        return h[:64] if h else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def checkout_run_branch(workspace_root: Path | str, branch: str) -> dict[str, Any]:
    """
    Phase 46 — isolate dev work on ``nexa/run-*`` branches when the tree allows it.

    Creates the branch with ``git checkout -b``; on failure (dirty/conflict), returns ok=False.
    """
    root = validate_workspace_path(str(workspace_root))
    b = (branch or "").strip()
    if not b or len(b) > 200:
        return {"ok": False, "error": "invalid_branch_name"}
    try:
        r = subprocess.run(
            ["git", "checkout", "-b", b],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120.0,
        )
        if r.returncode == 0:
            return {"ok": True, "branch": b}
        return {
            "ok": False,
            "error": "checkout_failed",
            "stderr": (r.stderr or "")[-4000:],
            "stdout": (r.stdout or "")[-2000:],
        }
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"ok": False, "error": str(exc)[:2000]}


def commit_quality_preflight(workspace_root: Path | str) -> dict[str, Any]:
    """Lightweight gate before committing (Phase 46 — production hygiene)."""
    root = validate_workspace_path(str(workspace_root))
    ufs = changed_files(root)
    gs = git_status(root)
    dirty = bool(ufs) or bool(str(gs.get("stdout") or "").strip())
    return {
        "ok": True,
        "has_changes": dirty,
        "changed_file_count": len(ufs),
    }


def repo_sanity_check(workspace_root: Path | str) -> dict[str, Any]:
    """Phase 47 — verify git is usable before heavy dev work.

    Repos without any commits yet are allowed (no HEAD); work may create the first commit.
    """
    root = validate_workspace_path(str(workspace_root))
    gs = git_status(root)
    if not gs.get("ok"):
        return {"ok": False, "error": "git_status_failed", "git_status": gs}
    head = rev_parse_head(root)
    if not head:
        return {"ok": True, "head": None, "empty_repo": True}
    return {"ok": True, "head": head[:64]}


def validate_commit(workspace_root: Path | str) -> dict[str, Any]:
    """
    Phase 47 — post-commit validation: git HEAD exists and repo tests pass.

    Intended immediately after a successful ``git commit``.
    """
    from app.services.dev_runtime.tester import run_repo_tests

    root = validate_workspace_path(str(workspace_root))
    rp = rev_parse_head(root)
    if not rp:
        return {"ok": False, "error": "missing_head_after_commit"}
    tests = run_repo_tests(root)
    ok = bool(tests.get("ok"))
    return {"ok": ok, "head": rp[:64], "tests": tests}


def rollback_last_commit(workspace_root: Path | str, *, allow_commit: bool) -> dict[str, Any]:
    """Undo the last commit on the current branch (dangerous; gated)."""
    if not allow_commit:
        return {"ok": False, "error": "rollback_not_allowed"}
    root = validate_workspace_path(str(workspace_root))
    try:
        r = subprocess.run(
            ["git", "reset", "--hard", "HEAD~1"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120.0,
        )
        return {
            "ok": r.returncode == 0,
            "returncode": r.returncode,
            "stderr": (r.stderr or "")[-4000:],
        }
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"ok": False, "error": str(exc)[:2000]}


def parse_github_slug_from_repo(workspace_root: Path | str) -> tuple[str, str] | None:
    """Return ``(owner, repo)`` from ``origin`` remote URL when it looks like GitHub."""
    root = validate_workspace_path(str(workspace_root))
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30.0,
        )
        if r.returncode != 0:
            return None
        url = (r.stdout or "").strip()
    except (subprocess.TimeoutExpired, OSError):
        return None
    # github.com:owner/repo.git or https://github.com/owner/repo.git
    m = re.search(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?(?:\s|$)", url, re.I)
    if not m:
        return None
    return (m.group(1), m.group(2).rstrip("/"))


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
    "changed_files",
    "checkout_run_branch",
    "commit_quality_preflight",
    "create_commit",
    "current_branch",
    "get_diff_summary",
    "git_diff",
    "git_status",
    "parse_github_slug_from_repo",
    "prepare_pr_summary",
    "repo_sanity_check",
    "rev_parse_head",
    "rollback_last_commit",
    "validate_commit",
]
