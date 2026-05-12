# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Database location helpers — Phase 60 unified SQLite for API + Telegram bot.

Resolves a single canonical file (default ``~/.aethos/data/aethos.db``) so API,
Telegram bot, and Mission Control share one database regardless of cwd.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import Any

from app.core.paths import get_default_database_path, get_default_sqlite_database_url


def canonical_database_path() -> Path:
    return get_default_database_path()


def canonical_database_url() -> str:
    return get_default_sqlite_database_url()


def _agent_count(db_path: Path) -> int:
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM aethos_orchestration_sub_agents"
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()
    except (OSError, sqlite3.Error):
        return 0


def discover_sqlite_files(*, repo_root: Path | None = None) -> list[Path]:
    home = Path.home()
    candidates = [
        home / ".aethos" / "overwhelm_reset.db",
        home / "aethos" / "overwhelm_reset.db",
        home / ".aethos" / "data" / "aethos.db",
        home / "aethos" / "data" / "aethos.db",
    ]
    if repo_root is not None:
        candidates.extend(
            [
                repo_root / "data" / "aethos.db",
                repo_root / "overwhelm_reset.db",
                repo_root / "data" / "overwhelm_reset.db",
            ]
        )
    out: list[Path] = []
    seen: set[str] = set()
    for p in candidates:
        try:
            rp = p.resolve()
        except OSError:
            continue
        key = str(rp)
        if key in seen:
            continue
        seen.add(key)
        if rp.is_file():
            out.append(rp)
    return out


def _pick_best_database(databases: list[Path]) -> tuple[Path | None, int]:
    """Pick file with most agent rows; tie-break: newer mtime."""
    best: Path | None = None
    best_count = -1
    best_mtime = 0.0

    for db in databases:
        if not db.is_file():
            continue
        c = _agent_count(db)
        try:
            mt = db.stat().st_mtime
        except OSError:
            mt = 0.0
        if c > best_count or (c == best_count and mt > best_mtime):
            best_count = c
            best_mtime = mt
            best = db
    if best is None:
        return None, 0
    return best, best_count


def _patch_database_url_in_env_files(url_line: str, env_files: list[Path]) -> None:
    seen: set[str] = set()
    for env_file in env_files:
        try:
            key = str(env_file.resolve())
        except OSError:
            key = str(env_file)
        if key in seen:
            continue
        seen.add(key)
        if not env_file.exists():
            continue
        try:
            lines = env_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        new_lines: list[str] = []
        replaced = False
        for line in lines:
            if line.startswith("DATABASE_URL="):
                if not replaced:
                    new_lines.append(url_line)
                    replaced = True
                continue
            new_lines.append(line)
        if not replaced:
            new_lines.append(url_line)
        try:
            env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        except OSError:
            pass


def _link_legacy_overwhelm_paths(canonical: Path, source_used: Path | None) -> None:
    home = Path.home()
    try:
        can_res = canonical.resolve()
    except OSError:
        return
    if not canonical.exists():
        return

    for legacy in (
        home / ".aethos" / "overwhelm_reset.db",
        home / "aethos" / "overwhelm_reset.db",
    ):
        try:
            if legacy.is_symlink():
                legacy.unlink(missing_ok=True)
                legacy.symlink_to(canonical)
                continue
            if not legacy.exists():
                legacy.symlink_to(canonical)
                continue
            if legacy.is_file():
                leg_res = legacy.resolve()
                if leg_res == can_res:
                    continue
                if source_used is not None and leg_res == source_used.resolve():
                    legacy.unlink()
                    legacy.symlink_to(canonical)
        except OSError:
            continue


def unify_databases(
    *,
    repo_root: Path | None = None,
    extra_env_files: list[Path] | None = None,
    update_env_files: bool = True,
    symlink_legacy_names: bool = True,
) -> dict[str, Any]:
    """
    Choose the existing SQLite file with the most rows in ``aethos_orchestration_sub_agents``
    (tie-break: newer mtime), copy it to the canonical path, then optionally align ``DATABASE_URL``
    in env files and replace legacy ``overwhelm_reset.db`` paths with symlinks when safe.
    """
    canonical = canonical_database_path()
    canonical.parent.mkdir(parents=True, exist_ok=True)
    url_line = f"DATABASE_URL={canonical_database_url()}"

    databases = discover_sqlite_files(repo_root=repo_root)
    if canonical.exists():
        databases.append(canonical)

    dedup: dict[str, Path] = {}
    for d in databases:
        try:
            dedup[str(d.resolve())] = d
        except OSError:
            dedup[str(d)] = d
    unique = list(dedup.values())

    best, best_count = _pick_best_database(unique)
    source_used: Path | None = best

    if best is not None:
        try:
            if best.resolve() != canonical.resolve():
                shutil.copy2(best, canonical)
        except OSError:
            pass
    elif not canonical.exists():
        try:
            canonical.touch()
        except OSError:
            pass

    final_agents = _agent_count(canonical)

    env_files: list[Path] = list(extra_env_files or [])
    if update_env_files:
        env_files.extend(
            [
                Path.home() / ".aethos" / ".env",
                Path.home() / "aethos" / ".env",
            ]
        )
        if repo_root is not None:
            env_files.append(repo_root / ".env")

    seen_env: set[str] = set()
    uniq_env: list[Path] = []
    for ep in env_files:
        try:
            k = str(ep.resolve())
        except OSError:
            k = str(ep)
        if k not in seen_env:
            seen_env.add(k)
            uniq_env.append(ep)

    _patch_database_url_in_env_files(url_line, uniq_env)

    if symlink_legacy_names:
        _link_legacy_overwhelm_paths(canonical, source_used)

    return {
        "canonical_path": canonical,
        "canonical_url": canonical_database_url(),
        "source_path": best,
        "agents_in_source": best_count,
        "agents_in_canonical": final_agents,
    }


def ensure_unified_database_for_setup(repo_root: Path | None = None) -> Path:
    """Run unification with repo and default env targets; return canonical DB path."""
    extra: list[Path] = []
    if repo_root is not None:
        extra.append(repo_root / ".env")
    unify_databases(repo_root=repo_root, extra_env_files=extra, update_env_files=True)
    return canonical_database_path()


__all__ = [
    "canonical_database_path",
    "canonical_database_url",
    "discover_sqlite_files",
    "ensure_unified_database_for_setup",
    "unify_databases",
]
