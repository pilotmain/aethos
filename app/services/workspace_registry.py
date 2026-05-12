# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Multi-project workspace registry: safe roots per owner."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.workspace_root import WorkspaceRoot

logger = logging.getLogger(__name__)


def normalize_root_path(raw: str) -> str:
    p = (raw or "").strip()
    if not p:
        raise ValueError("path is required")
    return str(Path(p).expanduser().resolve())


def list_roots(db: Session, owner_user_id: str, *, active_only: bool = True) -> list[WorkspaceRoot]:
    q = select(WorkspaceRoot).where(WorkspaceRoot.owner_user_id == owner_user_id)
    if active_only:
        q = q.where(WorkspaceRoot.is_active.is_(True))
    return list(db.scalars(q.order_by(WorkspaceRoot.id.asc())).all())


def add_root(
    db: Session,
    owner_user_id: str,
    path_raw: str,
    *,
    label: str | None = None,
) -> WorkspaceRoot:
    pn = normalize_root_path(path_raw)
    existing = db.scalars(
        select(WorkspaceRoot).where(
            WorkspaceRoot.owner_user_id == owner_user_id,
            WorkspaceRoot.path_normalized == pn,
        )
    ).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            if label:
                existing.label = label[:256]
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing
        raise ValueError(f"workspace root already registered: {pn}")
    row = WorkspaceRoot(
        owner_user_id=owner_user_id[:64],
        path_normalized=pn,
        label=(label or None) if label else None,
        is_active=True,
        metadata_json={},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("workspace_root added owner=%s path=%s", owner_user_id, pn)
    return row


def revoke_root(db: Session, owner_user_id: str, root_id: int) -> WorkspaceRoot | None:
    row = db.get(WorkspaceRoot, root_id)
    if not row or row.owner_user_id != owner_user_id:
        return None
    row.is_active = False
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def path_is_under_registered_root(db: Session, owner_user_id: str, candidate: Path) -> tuple[bool, Path | None]:
    """
    True if candidate resolves under at least one active registered root for owner.
    Returns (ok, matched_root_path).
    """
    try:
        c = candidate.resolve()
    except OSError:
        return False, None
    for r in list_roots(db, owner_user_id, active_only=True):
        root = Path(r.path_normalized).resolve()
        try:
            c.relative_to(root)
            return True, root
        except ValueError:
            continue
    return False, None


def default_work_root_path() -> Path:
    s = get_settings()
    raw = (getattr(s, "host_executor_work_root", None) or "").strip()
    from app.core.config import REPO_ROOT

    base = raw or str(REPO_ROOT)
    return Path(base).expanduser().resolve()


def path_allowed_under_policy(
    db: Session,
    owner_user_id: str,
    candidate: Path,
) -> tuple[bool, str]:
    """
    Enforce workspace registry + strict flag.

    When nexa_workspace_strict is false and the owner has no roots, allow paths under
    default_work_root_path() only (compat with single-root host executor).
    """
    s = get_settings()
    strict = bool(getattr(s, "nexa_workspace_strict", False))
    roots = list_roots(db, owner_user_id, active_only=True)
    try:
        c = candidate.resolve()
    except OSError as e:
        return False, f"invalid path: {e}"

    if roots:
        ok, matched = path_is_under_registered_root(db, owner_user_id, c)
        if ok:
            return True, ""
        return False, "path outside registered workspace roots — use /workspace add <path>"

    if strict:
        return False, "no workspace roots registered — add one with /workspace add <path>"

    dw = default_work_root_path()
    try:
        c.relative_to(dw)
        return True, ""
    except ValueError:
        return False, f"path outside default work root ({dw}) — register a workspace root or widen /workspace add"
