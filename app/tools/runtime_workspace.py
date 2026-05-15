"""Workspace list/search (scoped to ``~/.aethos/workspace``)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.core.paths import get_aethos_workspace_root


def workspace_list(*, max_entries: int = 200, max_depth: int = 4) -> dict[str, Any]:
    root = get_aethos_workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    out: list[str] = []

    def walk(d: Path, depth: int) -> None:
        if len(out) >= max_entries or depth > max_depth:
            return
        try:
            for name in sorted(os.listdir(d)):
                if len(out) >= max_entries:
                    return
                p = d / name
                rel = str(p.relative_to(root))
                if p.is_dir():
                    out.append(rel + "/")
                    walk(p, depth + 1)
                else:
                    out.append(rel)
        except OSError:
            return

    walk(root, 0)
    return {"tool": "workspace_list", "root": str(root.resolve()), "entries": out, "count": len(out)}


def workspace_search(substring: str, *, glob: str = "*", max_hits: int = 50) -> dict[str, Any]:
    root = get_aethos_workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    needle = (substring or "").lower()
    hits: list[dict[str, Any]] = []
    if not needle:
        return {"tool": "workspace_search", "hits": [], "count": 0}
    for path in root.rglob(glob):
        if len(hits) >= max_hits:
            break
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > 256_000:
                continue
            txt = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if needle in txt.lower():
            line_no = 1
            for i, line in enumerate(txt.splitlines(), start=1):
                if needle in line.lower():
                    line_no = i
                    break
            rel = str(path.relative_to(root))
            hits.append({"path": rel, "line": line_no})
    return {"tool": "workspace_search", "substring": substring, "hits": hits, "count": len(hits)}
