"""File read/write/patch under the AethOS workspace only."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from app.core.paths import get_aethos_workspace_root


def _resolve(rel: str) -> Path:
    p = (get_aethos_workspace_root() / (rel or "").lstrip("/")).resolve()
    root = get_aethos_workspace_root().resolve()
    p.relative_to(root)
    return p


def file_read(rel_path: str, *, max_bytes: int = 512_000) -> dict[str, Any]:
    try:
        p = _resolve(rel_path)
        if not p.is_file():
            return {"tool": "file_read", "path": rel_path, "ok": False, "error": "not a file"}
        data = p.read_bytes()[:max_bytes]
        h = hashlib.sha256(data).hexdigest()
        return {
            "tool": "file_read",
            "path": rel_path,
            "ok": True,
            "sha256": h,
            "content": data.decode("utf-8", errors="replace"),
        }
    except Exception as exc:  # noqa: BLE001
        return {"tool": "file_read", "path": rel_path, "ok": False, "error": str(exc)}


def file_write(rel_path: str, content: str) -> dict[str, Any]:
    try:
        p = _resolve(rel_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        before = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
        p.write_text(content or "", encoding="utf-8")
        after = hashlib.sha256(p.read_bytes()).hexdigest()
        return {
            "tool": "file_write",
            "path": rel_path,
            "ok": True,
            "before_sha256": before,
            "after_sha256": after,
            "bytes": len((content or "").encode("utf-8")),
        }
    except Exception as exc:  # noqa: BLE001
        return {"tool": "file_write", "path": rel_path, "ok": False, "error": str(exc)}


def file_patch(rel_path: str, old: str, new: str) -> dict[str, Any]:
    try:
        p = _resolve(rel_path)
        if not p.is_file():
            return {"tool": "file_patch", "path": rel_path, "ok": False, "error": "not a file"}
        text = p.read_text(encoding="utf-8", errors="replace")
        if old not in text:
            return {"tool": "file_patch", "path": rel_path, "ok": False, "error": "old text not found"}
        before = hashlib.sha256(text.encode("utf-8")).hexdigest()
        text2 = text.replace(old, new, 1)
        p.write_text(text2, encoding="utf-8")
        after = hashlib.sha256(text2.encode("utf-8")).hexdigest()
        return {"tool": "file_patch", "path": rel_path, "ok": True, "before_sha256": before, "after_sha256": after}
    except Exception as exc:  # noqa: BLE001
        return {"tool": "file_patch", "path": rel_path, "ok": False, "error": str(exc)}
