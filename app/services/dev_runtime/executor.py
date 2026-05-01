"""Allowlisted subprocess execution inside a workspace repo."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def _normalize_cmd(s: str) -> str:
    return " ".join((s or "").split())


def allowed_commands() -> frozenset[str]:
    s = get_settings()
    raw = (s.nexa_dev_allowed_commands or "").strip()
    parts = [_normalize_cmd(x) for x in raw.split(",") if x.strip()]
    return frozenset(parts)


def run_dev_command(workspace_root: Path | str, command: str) -> dict[str, Any]:
    """
    Run ``command`` with cwd = workspace_root.

    Command must match the allowlist exactly after whitespace normalization.
    """
    root = Path(workspace_root).resolve()
    if not root.is_dir():
        return {"ok": False, "error": "workspace_not_a_directory", "stdout": "", "stderr": ""}

    norm = _normalize_cmd(command)
    if norm not in allowed_commands():
        return {
            "ok": False,
            "error": "command_not_allowlisted",
            "detail": norm,
            "stdout": "",
            "stderr": "",
        }

    try:
        argv = shlex.split(norm)
    except ValueError as exc:
        return {"ok": False, "error": "invalid_command", "detail": str(exc), "stdout": "", "stderr": ""}

    if not argv:
        return {"ok": False, "error": "empty_argv", "stdout": "", "stderr": ""}

    timeout = max(5, int(get_settings().nexa_dev_command_timeout_seconds or 180))
    try:
        proc = subprocess.run(
            argv,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=float(timeout),
            env=None,
        )
        out = (proc.stdout or "")[-400_000:]
        err = (proc.stderr or "")[-200_000:]
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": out,
            "stderr": err,
            "command": norm,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "stdout": "", "stderr": "", "command": norm}
    except OSError as exc:
        return {"ok": False, "error": str(exc), "stdout": "", "stderr": "", "command": norm}


__all__ = ["allowed_commands", "run_dev_command"]
