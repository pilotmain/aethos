# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Resolve and validate a `Project` for ops execution (repo path, known keys)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.models.project import Project
from app.services.project_registry import get_default_project, get_project_by_key


def resolve_ops_project(
    db: Session,
    payload: dict,
    *,
    active_project_key: str | None = None,
) -> tuple[Project | None, str | None]:
    """
    Returns (project, error_user_message). Unknown explicit key → error; unconfigured → error.
    Priority: explicit `project_key` in payload, then active_project_key, then default project.
    """
    p = dict(payload or {})
    explicit = bool(p.get("project_key_explicit"))
    k = (p.get("project_key") or "").strip().lower() or None
    if not k and active_project_key:
        k = (active_project_key or "").strip().lower() or None
        explicit = False
    if not k:
        dp = get_default_project(db)
        if dp is None:
            return None, "Nexa: no default project. Run /projects or contact an admin."
        return dp, None
    proj = get_project_by_key(db, k)
    if proj is None and explicit:
        from app.services.project_registry import list_project_keys

        klist = (list_project_keys(db) or [])[:24] or ["(none)"]
        keys = ", ".join(klist)
        return None, f"Nexa: unknown project `{k}`.\n\nTry `/project add …` or pick one of: {keys}."
    if proj is None:
        return None, f"Nexa: project `{k}` is not available."
    return proj, None


def validate_project_repo(p: Project) -> str | None:
    """None if valid; else short error string."""
    r = (p.repo_path or "").strip()
    if not r:
        return f"Nexa: project `{p.key}` has no `repo_path` in Nexa. Set it in the DB (or /project add)."
    path = Path(r).expanduser().resolve()
    if not path.is_dir():
        return f"Nexa: project `{p.key}` repo path does not exist on the worker: `{path}`"
    return None
