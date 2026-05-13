# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Versioned snapshots for soul markdown (per-user DB soul + repo ``docs/development/soul.md``)."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings
from app.services.system_memory_files import soul_path


def _safe_user_segment(user_id: str) -> str:
    s = (user_id or "").strip()[:128] or "anonymous"
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", s)


def user_soul_history_dir(user_id: str) -> Path:
    return Path.home() / ".aethos" / "soul_history" / _safe_user_segment(user_id)


def repo_soul_history_dir() -> Path:
    return soul_path().parent / "soul_history"


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _history_limit() -> int:
    n = int(getattr(get_settings(), "nexa_soul_history_limit", 30) or 30)
    return max(1, min(n, 500))


def prune_soul_history(history_dir: Path, *, keep: int | None = None) -> None:
    keep_n = keep if keep is not None else _history_limit()
    if not history_dir.is_dir():
        return
    versions = sorted(history_dir.glob("*.md"), key=lambda p: p.name, reverse=True)
    for old in versions[keep_n:]:
        try:
            if old.is_file():
                old.unlink()
        except OSError:
            pass


def snapshot_user_soul_before_write(user_id: str, previous_markdown: str) -> str | None:
    """Persist *previous* soul markdown before a DB update (newest snapshots first by filename sort)."""
    prev = (previous_markdown or "").strip()
    if not prev:
        return None
    hist = user_soul_history_dir(user_id)
    _ensure_dir(hist)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    out = hist / f"{stamp}.md"
    out.write_text(previous_markdown, encoding="utf-8")
    prune_soul_history(hist)
    return str(out)


def snapshot_repo_soul_file() -> str | None:
    """Copy current ``docs/development/soul.md`` into ``soul_history/`` before it is overwritten."""
    src = soul_path()
    if not src.is_file():
        return None
    hist = repo_soul_history_dir()
    _ensure_dir(hist)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    dest = hist / f"{stamp}.md"
    shutil.copy2(src, dest)
    prune_soul_history(hist)
    return str(dest)


def get_user_soul_history(user_id: str, limit: int | None = None) -> list[str]:
    hist = user_soul_history_dir(user_id)
    if not hist.is_dir():
        return []
    lim = limit if limit is not None else _history_limit()
    versions = sorted(hist.glob("*.md"), key=lambda p: p.name, reverse=True)
    return [p.stem for p in versions[:lim]]


def read_user_soul_version(user_id: str, version: str) -> str | None:
    stem = (version or "").strip()
    if not stem or ".." in stem or "/" in stem or "\\" in stem:
        return None
    p = user_soul_history_dir(user_id) / f"{stem}.md"
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def get_repo_soul_history(limit: int | None = None) -> list[str]:
    hist = repo_soul_history_dir()
    if not hist.is_dir():
        return []
    lim = limit if limit is not None else _history_limit()
    versions = sorted(hist.glob("*.md"), key=lambda p: p.name, reverse=True)
    return [p.stem for p in versions[:lim]]


def read_repo_soul_version(version: str) -> str | None:
    stem = (version or "").strip()
    if not stem or ".." in stem or "/" in stem or "\\" in stem:
        return None
    p = repo_soul_history_dir() / f"{stem}.md"
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


__all__ = [
    "get_repo_soul_history",
    "get_user_soul_history",
    "read_repo_soul_version",
    "read_user_soul_version",
    "repo_soul_history_dir",
    "snapshot_repo_soul_file",
    "snapshot_user_soul_before_write",
    "user_soul_history_dir",
]
