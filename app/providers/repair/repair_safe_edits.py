# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Safe in-workspace edit execution with checkpoints (Phase 2 Step 7)."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

_PROTECTED_PARTS = frozenset(
    {
        ".env",
        ".git",
        "node_modules",
        ".ssh",
        ".aws",
    }
)
_PROTECTED_SUFFIXES = (".pem", ".key")


def is_protected_relative_path(rel: str) -> bool:
    p = Path((rel or "").strip().lstrip("/"))
    parts = [x.lower() for x in p.parts]
    if not parts:
        return False
    if parts[0] in _PROTECTED_PARTS:
        return True
    if any(part in _PROTECTED_PARTS for part in parts):
        return True
    name = parts[-1]
    if name.startswith(".env"):
        return True
    return name.endswith(_PROTECTED_SUFFIXES)


def _checkpoint_dir(repo: Path) -> Path:
    d = repo / ".aethos" / "repair_checkpoints"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _create_checkpoint(repo: Path, target: Path) -> str | None:
    if not target.is_file():
        return None
    cid = str(uuid.uuid4())
    dest = _checkpoint_dir(repo) / f"{cid}_{target.name}"
    try:
        shutil.copy2(target, dest)
    except OSError:
        return None
    return cid


def apply_safe_edit(repo: Path, step: dict[str, Any]) -> dict[str, Any]:
    rel = str(step.get("path") or "")
    if is_protected_relative_path(rel):
        return {"ok": False, "error": "protected_path", "path": rel}
    target = (repo / rel.lstrip("/")).resolve()
    try:
        target.relative_to(repo.resolve())
    except ValueError:
        return {"ok": False, "error": "path_escape", "path": rel}

    op = str(step.get("operation") or "patch").lower()
    checkpoint_id = _create_checkpoint(repo, target) if target.is_file() else None
    content = step.get("content")
    patch = step.get("patch")

    try:
        if op == "replace" and isinstance(content, str):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        elif op == "append" and isinstance(content, str):
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as fh:
                fh.write(content)
        elif op == "patch":
            if isinstance(content, str) and content.strip():
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_file():
                    existing = target.read_text(encoding="utf-8", errors="replace")
                    target.write_text(existing + content, encoding="utf-8")
                else:
                    target.write_text(content, encoding="utf-8")
            elif isinstance(patch, str) and patch.strip() and target.is_file():
                existing = target.read_text(encoding="utf-8", errors="replace")
                if patch not in existing:
                    target.write_text(existing.replace(patch, "", 1) if patch in existing else existing + patch, encoding="utf-8")
            else:
                return {"ok": False, "error": "empty_patch", "path": rel}
        else:
            return {"ok": False, "error": "unsupported_operation", "path": rel}
    except OSError as exc:
        return {"ok": False, "error": str(exc), "path": rel, "checkpoint_id": checkpoint_id}

    return {
        "ok": True,
        "path": rel,
        "operation": op,
        "checkpoint_id": checkpoint_id,
        "reason": step.get("reason"),
    }
