# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Restart and reconnect commands (Phase 4 Step 4)."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _pkill_pattern(pattern: str) -> None:
    try:
        subprocess.run(["pkill", "-f", pattern], capture_output=True, timeout=5.0)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _start_api(repo: Path, *, reload: bool = True) -> subprocess.Popen | None:
    py = repo / ".venv" / "bin" / "python"
    if not py.is_file():
        py = Path(sys.executable)
    port = os.environ.get("AETHOS_SERVE_PORT") or os.environ.get("NEXA_SERVE_PORT") or "8010"
    cmd = [str(py), "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port)]
    if reload:
        cmd.append("--reload")
    try:
        return subprocess.Popen(cmd, cwd=str(repo), start_new_session=True)
    except OSError:
        return None


def _start_web(repo: Path) -> subprocess.Popen | None:
    web = repo / "web"
    if not (web / "package.json").is_file():
        return None
    npm = "npm"
    try:
        return subprocess.Popen(
            [npm, "run", "dev"],
            cwd=str(web),
            start_new_session=True,
            env={**os.environ, "PORT": "3000"},
        )
    except OSError:
        return None


def cmd_restart(target: str = "all") -> int:
    repo = _repo_root()
    target = (target or "all").lower()
    if target in ("all", "api"):
        _pkill_pattern("uvicorn app.main:app")
    if target in ("all", "web"):
        _pkill_pattern("next dev")
    if target in ("all", "bot"):
        _pkill_pattern("app.bot.telegram_bot")
    time.sleep(1.0)
    if target in ("all", "api"):
        proc = _start_api(repo)
        print(f"API {'started' if proc else 'failed'} (port {os.environ.get('AETHOS_SERVE_PORT', '8010')})")
    if target in ("all", "web"):
        proc = _start_web(repo)
        print(f"Mission Control web {'started' if proc else 'skipped — no web/package.json'}")
    if target == "connection":
        from aethos_cli.connection_cli import cmd_connection_repair

        return cmd_connection_repair()
    from aethos_cli.cli_status import cmd_status

    return cmd_status()
