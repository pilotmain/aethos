"""Guards for autonomous agent: clean tree, no direct edits on main."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from app.services.handoff_paths import PROJECT_ROOT

ROOT = str(PROJECT_ROOT)


def _env_allow_dirty() -> bool:
    return (os.getenv("DEV_AGENT_ALLOW_DIRTY_TREE", "false") or "false").strip().lower() in {
        "1", "true", "yes", "y", "on",
    }


def ensure_clean_worktree(cwd: str | Path | None = None) -> None:
    if _env_allow_dirty():
        return
    c = str(cwd or ROOT)
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=c,
        text=True,
        capture_output=True,
    )
    if r.returncode != 0:
        return
    if (r.stdout or "").strip():
        raise RuntimeError(
            "Dev Agent paused because the repo has uncommitted changes.\n\n"
            "Run:\n"
            "git status\n\n"
            "Then choose:\n"
            "1. commit the changes\n"
            "2. stash them\n"
            "3. discard them\n\n"
            "I won’t run autonomous code changes on a dirty repo because that could mix unrelated work.\n\n"
            "If you are sure, you can set DEV_AGENT_ALLOW_DIRTY_TREE=true (not recommended for isolation)."
        )


def current_branch(cwd: str | Path | None = None) -> str:
    c = str(cwd or ROOT)
    p = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=c,
        text=True,
        capture_output=True,
    )
    if p.returncode != 0:
        return "?"
    return (p.stdout or "").strip() or "?"


def is_mainish(branch: str) -> bool:
    b = (branch or "").casefold()
    return b in {"main", "master", "head"}


def ensure_not_on_main_for_new_branch(
    create_branch_fn, *, cwd: str | Path | None = None
) -> None:
    br = current_branch(cwd)
    if is_mainish(br):
        create_branch_fn()
