# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Resolve the directory that should be treated as the deployable project root."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

# Junk dirs to skip when scanning immediate children for a nested project.
_SKIP_CHILD_NAMES = frozenset(
    {
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "ENV",
        "dist",
        "build",
        ".next",
        "__pycache__",
        ".turbo",
        "coverage",
        "htmlcov",
    }
)


def _has_project_marker(path: Path) -> bool:
    """True if ``path`` looks like an app root (package.json, pyproject, src/, etc.)."""
    file_markers = (
        "package.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "pyproject.toml",
        "requirements.txt",
        "Cargo.toml",
        "go.mod",
        "index.html",
        "vercel.json",
        "vercel.toml",
        "railway.toml",
        "railway.json",
        "fly.toml",
        "netlify.toml",
        "wrangler.toml",
        "next.config.js",
        "next.config.mjs",
        "next.config.ts",
        "vite.config.js",
        "vite.config.ts",
        "app.js",
    )
    dir_markers = ("src", "public", "app", "pages", "web")
    for name in file_markers:
        if (path / name).is_file():
            return True
    for d in dir_markers:
        if (path / d).is_dir():
            return True
    return False


def find_project_root(start_path: str | Path) -> Path:
    """
    Prefer a subdirectory that contains the real app when ``start_path`` is only a workspace
    folder (e.g. contains a lone ``index.html`` or empty scaffold).
    """
    path = Path(start_path).expanduser().resolve()
    if not path.is_dir():
        return path

    if _has_project_marker(path):
        return path

    try:
        children = sorted(p for p in path.iterdir() if p.is_dir())
    except OSError:
        return path

    candidates: list[Path] = []
    for child in children:
        if child.name.startswith(".") or child.name in _SKIP_CHILD_NAMES:
            continue
        if _has_project_marker(child):
            candidates.append(child)

    if len(candidates) == 1:
        return candidates[0].resolve()
    if len(candidates) > 1:
        # Ambiguous; stay at workspace root so detection / CLI errors surface clearly.
        return path
    return path


def count_deploy_files(root: Path, *, limit: int = 50_000) -> int:
    """Bounded file count under ``root`` (for chat summaries)."""
    n = 0
    try:
        for p in root.rglob("*"):
            if p.is_file():
                n += 1
                if n >= limit:
                    return limit
    except OSError:
        pass
    return n


def git_context(root: Path) -> dict[str, Any]:
    """Best-effort git branch / commit / remote for deployment summaries."""
    out: dict[str, Any] = {}
    if not root.is_dir():
        return out
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=8,
        )
        if r.returncode != 0 or (r.stdout or "").strip() != "true":
            return out
    except (OSError, subprocess.TimeoutExpired):
        return out

    def _run(args: list[str]) -> str | None:
        try:
            pr = subprocess.run(
                ["git", *args],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=8,
            )
            if pr.returncode != 0:
                return None
            s = (pr.stdout or "").strip()
            return s or None
        except (OSError, subprocess.TimeoutExpired):
            return None

    branch = _run(["rev-parse", "--abbrev-ref", "HEAD"])
    commit = _run(["rev-parse", "--short", "HEAD"])
    remote = _run(["remote", "get-url", "origin"])
    if branch:
        out["git_branch"] = branch
    if commit:
        out["git_commit"] = commit
    if remote:
        out["git_remote"] = remote
    return out


def bundle_deploy_metadata(project_root: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {"project_root": str(project_root.resolve())}
    meta["deployed_files"] = count_deploy_files(project_root)
    meta.update(git_context(project_root))
    return meta


__all__ = ["find_project_root", "bundle_deploy_metadata", "count_deploy_files", "git_context"]
