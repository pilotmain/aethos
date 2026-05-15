"""Allowlisted shell execution under the AethOS workspace (OpenClaw parity)."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from app.core.paths import get_aethos_workspace_root
from app.services.host_executor import is_command_safe


def run_shell_command(command: str, *, cwd: Path | None = None, timeout_sec: float = 120.0) -> dict[str, Any]:
    """
    Run ``command`` with ``cwd`` defaulting to ``~/.aethos/workspace``.
    Requires :func:`~app.services.host_executor.is_command_safe`.
    """
    cmd = (command or "").strip()
    if not cmd or not is_command_safe(cmd):
        return {
            "tool": "shell",
            "command": cmd,
            "cwd": str(cwd or get_aethos_workspace_root()),
            "returncode": -1,
            "ok": False,
            "stdout": "",
            "stderr": "command rejected by allowlist",
            "started_at": None,
            "completed_at": None,
        }
    root = cwd or get_aethos_workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        rc = int(proc.returncode)
        out = proc.stdout or ""
        err = proc.stderr or ""
    except subprocess.TimeoutExpired:
        rc = -9
        out = ""
        err = f"timeout after {timeout_sec}s"
    except OSError as exc:
        rc = -1
        out = ""
        err = str(exc)
    done = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "tool": "shell",
        "command": cmd,
        "cwd": str(root.resolve()),
        "returncode": rc,
        "ok": rc == 0,
        "stdout": out[-200_000:],
        "stderr": err[-50_000:],
        "duration_sec": round(time.time() - t0, 3),
        "started_at": started,
        "completed_at": done,
    }
