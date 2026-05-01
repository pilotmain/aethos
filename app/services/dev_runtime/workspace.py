"""Register and validate dev workspaces (path confinement)."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.models.dev_runtime import NexaDevWorkspace


def allowed_workspace_roots() -> list[Path]:
    s = get_settings()
    raw = (s.nexa_dev_workspace_roots or "").strip()
    out: list[Path] = []
    if raw:
        for part in raw.split(","):
            p = part.strip()
            if p:
                out.append(Path(p).expanduser().resolve())
    else:
        out.append(Path(s.nexa_workspace_root).expanduser().resolve())
        out.append(REPO_ROOT.resolve())
    return out


def validate_workspace_path(repo_path: str) -> Path:
    """Resolve path and ensure it stays under an allowed root (no traversal)."""
    p = Path(repo_path).expanduser().resolve()
    if not p.is_dir():
        raise ValueError("repo_path is not a directory")
    for root in allowed_workspace_roots():
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise ValueError(
        "repo_path must be under an allowed workspace root "
        "(set NEXA_DEV_WORKSPACE_ROOTS or use paths under NEXA_WORKSPACE_ROOT / repo root)"
    )


def register_workspace(
    db: Session,
    user_id: str,
    name: str,
    repo_path: str,
    *,
    repo_url: str | None = None,
    branch: str | None = None,
) -> NexaDevWorkspace:
    root = validate_workspace_path(repo_path)
    wid = str(uuid.uuid4())
    row = NexaDevWorkspace(
        id=wid,
        user_id=user_id,
        name=(name or root.name)[:512],
        repo_path=str(root),
        repo_url=(repo_url or "").strip()[:2000] or None,
        branch=(branch or "").strip()[:512] or None,
        status="ready",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_workspace(db: Session, user_id: str, workspace_id: str) -> NexaDevWorkspace | None:
    row = db.get(NexaDevWorkspace, workspace_id)
    if row is None or row.user_id != user_id:
        return None
    return row


def list_workspaces(db: Session, user_id: str, *, limit: int = 100) -> list[NexaDevWorkspace]:
    from sqlalchemy import select

    q = (
        select(NexaDevWorkspace)
        .where(NexaDevWorkspace.user_id == user_id)
        .order_by(NexaDevWorkspace.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(q).all())


__all__ = [
    "allowed_workspace_roots",
    "validate_workspace_path",
    "register_workspace",
    "get_workspace",
    "list_workspaces",
]
