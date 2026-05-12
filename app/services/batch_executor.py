# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Batch file creation helpers for NL gateway shortcuts (workspace-scoped)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def create_batch_files(
    files: list[dict[str, Any]],
    workspace_root: str,
    user_id: str,
) -> dict[str, Any]:
    """Create multiple files under ``workspace_root`` (relative paths only)."""
    _ = user_id
    root = Path(workspace_root).expanduser().resolve()
    results: list[dict[str, Any]] = []
    for file_info in files:
        name = str(file_info.get("filename") or "").strip().replace("\\", "/").lstrip("/")
        if not name or ".." in Path(name).parts:
            continue
        filepath = (root / name).resolve()
        try:
            filepath.relative_to(root)
        except ValueError:
            continue
        filepath.parent.mkdir(parents=True, exist_ok=True)
        body = str(file_info.get("content", ""))
        filepath.write_text(body, encoding="utf-8")
        results.append(
            {
                "filename": name,
                "path": str(filepath),
                "size": len(body.encode("utf-8", errors="replace")),
            }
        )
    return {"success": bool(results), "files": results, "count": len(results)}


def parse_batch_create_intent(text: str) -> dict[str, Any] | None:
    """Parse natural language batch file creation intent."""
    if not text or not isinstance(text, str):
        return None
    text_lower = text.strip().splitlines()[0].strip().lower()
    if not text_lower:
        return None

    patterns = [
        r"create\s+(?:a|an)\s+(\w+)\s+app\s+with\s+(.+)",
        r"create\s+files?\s+(.+)",
        r"make\s+(?:a|an)\s+(\w+)\s+project\s+with\s+(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if not match:
            continue
        groups = match.groups()
        if len(groups) >= 2:
            project_name = (match.group(1) or "project").strip()
            files_str = (match.group(2) or "").strip()
        else:
            project_name = "project"
            files_str = (match.group(1) or "").strip()
        file_names = [f.strip() for f in files_str.split(",") if f.strip()]
        if not file_names:
            return None
        return {
            "intent": "batch_create",
            "project_name": project_name,
            "files": [{"filename": f, "content": f"// {f}\n"} for f in file_names],
        }
    return None
