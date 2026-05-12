# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Sandboxed local file/shell helpers — privacy-gated (Phase 22)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings


def _workspace_cap_root(user_id: str) -> Path:
    base = (get_settings().nexa_workspace_root or "").strip() or str(REPO_ROOT / "aethos_workspace")
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in user_id)[:64]
    root = Path(base) / "users" / safe
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def read_file_sandboxed(relative_path: str, *, user_id: str, db: Session | None = None) -> dict[str, Any]:
    _ = db
    s = get_settings()
    if not s.nexa_agent_tools_enabled:
        return {"ok": False, "error": "agent_tools_disabled"}
    if s.nexa_privacy_firewall_enabled and ".." in relative_path.replace("\\", "/"):
        return {"ok": False, "error": "path_not_allowed"}
    root = _workspace_cap_root(user_id)
    target = (root / relative_path.lstrip("/")).resolve()
    if root not in target.parents and target != root:
        return {"ok": False, "error": "path_outside_workspace"}
    if not target.is_file():
        return {"ok": False, "error": "not_found"}
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
        return {"ok": True, "path": str(target.relative_to(root)), "content": text[:200_000]}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def run_shell_restricted(
    argv: list[str],
    *,
    user_id: str,
    db: Session | None = None,
) -> dict[str, Any]:
    _ = db
    s = get_settings()
    if not s.nexa_agent_tools_enabled:
        return {"ok": False, "error": "agent_tools_disabled"}
    if not argv:
        return {"ok": False, "error": "empty_argv"}
    cmd0 = (argv[0] or "").lower()
    if cmd0 not in {"echo", "pwd", "ls", "date", "uname"}:
        return {"ok": False, "error": "command_not_allowlisted"}
    import subprocess

    try:
        cp = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(_workspace_cap_root(user_id)),
            env={**os.environ, "PATH": "/usr/bin:/bin"},
        )
        return {
            "ok": cp.returncode == 0,
            "stdout": (cp.stdout or "")[:50_000],
            "stderr": (cp.stderr or "")[:20_000],
            "code": cp.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


__all__ = ["read_file_sandboxed", "run_shell_restricted"]
