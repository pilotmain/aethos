# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.projects.vercel_link import read_package_name, read_vercel_project_link, slugify_project_id

_MARKERS = (
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "vercel.json",
    "railway.json",
    "netlify.toml",
    "fly.toml",
    "wrangler.toml",
    ".git",
)

_SKIP_DIR_NAMES = frozenset(
    {"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".turbo"}
)


def _parse_search_roots(raw: str, *, workspace_fallback: Path) -> list[Path]:
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    roots: list[Path] = []
    for p in parts:
        roots.append(Path(p).expanduser().resolve())
    if not roots:
        roots.append(workspace_fallback)
    return roots


def discover_local_projects(
    *,
    settings: Settings | None = None,
    max_roots: int = 12,
    max_candidates: int = 200,
) -> list[dict[str, Any]]:
    """
    Walk configured roots up to ``aethos_project_discovery_depth`` and collect project candidates.

    Markers gate inclusion (``package.json``, ``pyproject.toml``, ``.git``, deploy configs, …).
    """
    s = settings or get_settings()
    from app.core.paths import get_aethos_workspace_root

    depth = int(getattr(s, "aethos_project_discovery_depth", 3) or 3)
    depth = max(1, min(depth, 12))
    raw_roots = str(getattr(s, "aethos_project_search_roots", "") or "").strip()
    roots = _parse_search_roots(raw_roots, workspace_fallback=get_aethos_workspace_root())[:max_roots]

    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    for root in roots:
        if not root.is_dir():
            continue
        root = root.resolve()
        for dirpath, dirnames, _filenames in os.walk(root, topdown=True):
            p = Path(dirpath)
            try:
                rel_depth = len(p.relative_to(root).parts)
            except ValueError:
                continue
            if rel_depth > depth:
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIR_NAMES]
            markers = [m for m in _MARKERS if (p / m).exists()]
            if not markers:
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            pkg_name = read_package_name(p)
            slug = slugify_project_id(pkg_name or p.name)
            vlink = read_vercel_project_link(p)
            links: list[dict[str, Any]] = []
            if vlink:
                links.append(vlink)
            found.append(
                {
                    "project_id": slug,
                    "name": pkg_name or p.name,
                    "aliases": sorted({slug, (pkg_name or "").lower(), p.name.lower()} - {""}),
                    "repo_path": key,
                    "markers": markers,
                    "provider_links": links,
                    "detected_files": [m for m in markers if m != ".git"][:20],
                }
            )
            if len(found) >= max_candidates:
                return found
    return found
