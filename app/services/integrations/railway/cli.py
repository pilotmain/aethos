"""
Bounded Railway CLI invocations for Phase 58 — read-only / diagnostic only.

Never runs deploy, up, shell, or arbitrary user text. Subprocess argv is built
entirely from this module + runner (fixed templates).
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

# First argument after `railway` — diagnostic / read-only surface only.
_ALLOWED_SUBCOMMANDS = frozenset({"whoami", "status", "logs"})


def railway_binary_on_path() -> bool:
    return shutil.which("railway") is not None


def run_railway_cli(
    subcommand: str,
    extra_args: list[str] | None,
    *,
    cwd: str | None = None,
    timeout: float = 45.0,
) -> dict[str, Any]:
    """
    Run ``railway <subcommand> ...`` with optional cwd (linked project dir).

    ``extra_args`` must be safe fragments only — validated below.
    """
    sub = (subcommand or "").strip().lower()
    if sub not in _ALLOWED_SUBCOMMANDS:
        return {
            "ok": False,
            "error": "railway_subcommand_not_allowed",
            "detail": sub,
            "stdout": "",
            "stderr": "",
        }

    extras = list(extra_args or [])
    if sub != "logs" and extras:
        return {
            "ok": False,
            "error": "extra_args_not_allowed_for_subcommand",
            "detail": sub,
            "stdout": "",
            "stderr": "",
        }
    if sub == "logs":
        # Only allow benign tail/limit flags (no user-controlled strings).
        if extras and extras != ["--tail", "100"]:
            allowed_logs_patterns = (["--tail", "100"], ["--tail", "50"], [])
            if extras not in allowed_logs_patterns:
                return {
                    "ok": False,
                    "error": "railway_logs_args_not_allowed",
                    "detail": str(extras),
                    "stdout": "",
                    "stderr": "",
                }

    if not railway_binary_on_path():
        return {
            "ok": False,
            "error": "railway_cli_missing",
            "stdout": "",
            "stderr": "",
        }

    argv = ["railway", sub, *extras]
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=None,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-120_000:],
            "stderr": (proc.stderr or "")[-80_000:],
            "argv": argv,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "stdout": "", "stderr": "", "argv": argv}
    except OSError as exc:
        return {"ok": False, "error": str(exc), "stdout": "", "stderr": "", "argv": argv}


__all__ = ["railway_binary_on_path", "run_railway_cli"]
