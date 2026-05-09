"""Offline / bundled marketplace catalog when the remote ClawHub registry is unreachable."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT, Settings

logger = logging.getLogger(__name__)


def _resolved_catalog_path(settings: Settings) -> Path | None:
    raw = (getattr(settings, "nexa_clawhub_fallback_catalog_path", None) or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p

_BUILTIN_SKILLS: list[dict[str, Any]] = [
    {
        "name": "github",
        "version": "1.0.0",
        "description": "GitHub repository management (built-in fallback stub).",
        "author": "aethos",
        "publisher": "builtin",
        "tags": ["git", "devops"],
        "category": "devops",
        "downloads": 120000,
        "rating": 4.6,
        "updated_at": "2026-01-01T00:00:00Z",
    },
    {
        "name": "telegram",
        "version": "1.0.0",
        "description": "Telegram messaging integration (built-in fallback stub).",
        "author": "aethos",
        "publisher": "builtin",
        "tags": ["messaging"],
        "category": "messaging",
        "downloads": 145000,
        "rating": 4.5,
        "updated_at": "2026-01-01T00:00:00Z",
    },
]


def _parse_catalog_file(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("fallback catalog unreadable %s: %s", path, exc)
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        inner = raw.get("skills") or raw.get("items") or raw.get("results")
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
    return []


def merged_fallback_skill_dicts(settings: Settings) -> list[dict[str, Any]]:
    """Merge JSON catalog (if configured + present) over built-in stubs; dedupe by ``name``."""

    file_rows: list[dict[str, Any]] = []
    rp = _resolved_catalog_path(settings)
    if rp is not None:
        file_rows = _parse_catalog_file(rp)

    by_name: dict[str, dict[str, Any]] = {}
    for row in _BUILTIN_SKILLS:
        nm = str(row.get("name") or "").strip().lower()
        if nm:
            by_name[nm] = dict(row)
    for row in file_rows:
        nm = str(row.get("name") or "").strip().lower()
        if nm:
            by_name[nm] = {**by_name.get(nm, {}), **row}
    return list(by_name.values())


def filter_skill_dicts(
    rows: list[dict[str, Any]],
    *,
    query: str,
    category: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    q = (query or "").strip().lower()
    cat = (category or "").strip().lower()
    out: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("name") or "").lower()
        desc = str(row.get("description") or "").lower()
        row_cat = str(row.get("category") or "").lower()
        tags = row.get("tags") if isinstance(row.get("tags"), list) else []
        tag_l = [str(t).lower() for t in tags]
        if cat and row_cat != cat:
            continue
        if q:
            if q not in name and q not in desc and not any(q in t for t in tag_l):
                continue
        out.append(row)
        if len(out) >= max(1, limit):
            break
    return out


def sort_by_downloads(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(r: dict[str, Any]) -> int:
        try:
            return int(r.get("downloads") or 0)
        except (TypeError, ValueError):
            return 0

    return sorted(rows, key=key, reverse=True)


def find_skill_dict(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    nm = (name or "").strip().lower()
    if not nm:
        return None
    for row in rows:
        if str(row.get("name") or "").strip().lower() == nm:
            return row
    return None


__all__ = [
    "find_skill_dict",
    "filter_skill_dicts",
    "merged_fallback_skill_dicts",
    "sort_by_downloads",
]
