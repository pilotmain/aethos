"""
Resolve a filesystem root for orchestration / QA scans without repeatedly asking the user.

Prefer an explicit path hint, then DB-registered workspace roots, then :envvar:`NEXA_WORKSPACE_ROOT`,
then :func:`~app.services.workspace_registry.default_work_root_path`, then cwd.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.services.workspace_registry import default_work_root_path, list_roots

# Absolute paths in user text (Unix-style); strip trailing punctuation after match.
_PATH_IN_TEXT = re.compile(r"(?P<p>/Users/\S+|/(?:home|var|tmp)/\S+|/[a-zA-Z0-9][^\s:`\"]*)")


def extract_path_hint_from_message(message: str) -> str | None:
    """Return first plausible absolute path from free text if it exists on disk."""
    text = (message or "").strip()
    if not text:
        return None
    for m in _PATH_IN_TEXT.finditer(text):
        raw = m.group("p").rstrip(".,;)'\"")
        p = Path(raw).expanduser()
        try:
            if p.exists():
                return str(p.resolve())
        except OSError:
            continue
    # Single-token absolute path
    first = text.split()[0] if text.split() else ""
    if first.startswith("/"):
        p = Path(first).expanduser()
        try:
            if p.exists():
                return str(p.resolve())
        except OSError:
            pass
    return None


def resolve_workspace_path(
    path_hint: str | None,
    *,
    db: Session | None,
    owner_user_id: str | None,
) -> Path:
    """
    Resolve directory root for repo scans. Does not require Telegram chat_id — use ``owner_user_id``
    with ``db`` for registered workspace roots (same model as /workspace add).
    """
    if path_hint:
        p = Path(path_hint).expanduser()
        try:
            if p.is_dir():
                return p.resolve()
            if p.is_file():
                return p.resolve().parent
        except OSError:
            pass

    uid = (owner_user_id or "").strip()
    if db is not None and uid:
        roots = list_roots(db, uid, active_only=True)
        if roots:
            return Path(roots[0].path_normalized).resolve()

    s = get_settings()
    nw = (getattr(s, "nexa_workspace_root", None) or "").strip()
    if nw:
        pp = Path(nw).expanduser()
        if pp.exists():
            return pp.resolve()

    dw = default_work_root_path()
    if dw.exists():
        return dw

    repo = Path(REPO_ROOT)
    if repo.exists():
        return repo.resolve()

    cwd = Path.cwd()
    if cwd.exists():
        return cwd.resolve()

    raise ValueError(
        "No workspace root found. Set NEXA_WORKSPACE_ROOT, register a root via /workspace add <path>, "
        "or pass an absolute path in your message."
    )


__all__ = ["extract_path_hint_from_message", "resolve_workspace_path"]
