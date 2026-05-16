# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def read_vercel_project_link(repo_root: Path) -> dict[str, Any] | None:
    """Parse ``.vercel/project.json`` when present."""
    p = repo_root / ".vercel" / "project.json"
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    pid = str(data.get("projectId") or "").strip()
    org = str(data.get("orgId") or "").strip()
    if not pid and not org:
        return None
    name = repo_root.name
    return {
        "provider": "vercel",
        "project_id": pid or None,
        "org_id": org or None,
        "project_name": str(data.get("projectName") or name).strip() or name,
        "repo_path": str(repo_root.resolve()),
    }


def read_package_name(repo_root: Path) -> str | None:
    pkg = repo_root / "package.json"
    if not pkg.is_file():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    nm = str(data.get("name") or "").strip()
    return nm or None


def slugify_project_id(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:80] or "project"
