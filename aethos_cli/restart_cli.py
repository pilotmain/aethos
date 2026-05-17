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
    from app.services.mission_control.runtime_restart_manager import record_restart_event

    repo = _repo_root()
    target = (target or "all").lower()
    ok = True
    if target == "runtime":
        from app.services.mission_control.runtime_ownership_lock import (
            record_process_lifecycle_event,
            release_runtime_ownership_if_owner,
            try_acquire_runtime_ownership,
        )
        from app.services.telegram_polling_lock import release_telegram_polling_lock_if_owner

        release_runtime_ownership_if_owner()
        release_telegram_polling_lock_if_owner()
        _pkill_pattern("uvicorn app.main:app")
        _pkill_pattern("app.bot.telegram_bot")
        time.sleep(1.0)
        port = int(os.environ.get("AETHOS_SERVE_PORT") or os.environ.get("NEXA_SERVE_PORT") or "8010")
        try_acquire_runtime_ownership(role="cli", port=port, force=True)
        proc = _start_api(repo)
        ok = proc is not None
        print(f"Runtime API {'started' if proc else 'failed'} (port {port})")
        record_restart_event("runtime", ok=ok, detail="runtime supervision restart")
        record_process_lifecycle_event("restart_runtime", service="api")
        from aethos_cli.cli_status import cmd_status

        return cmd_status()
    if target in ("all", "api"):
        _pkill_pattern("uvicorn app.main:app")
    if target in ("all", "web"):
        _pkill_pattern("next dev")
    if target in ("all", "bot"):
        _pkill_pattern("app.bot.telegram_bot")
    time.sleep(1.0)
    if target in ("all", "api"):
        proc = _start_api(repo)
        ok = ok and proc is not None
        print(f"API {'started' if proc else 'failed'} (port {os.environ.get('AETHOS_SERVE_PORT', '8010')})")
        record_restart_event("api", ok=proc is not None)
    if target in ("all", "web"):
        proc = _start_web(repo)
        ok = ok and (proc is not None or not (repo / "web" / "package.json").is_file())
        print(f"Mission Control web {'started' if proc else 'skipped — no web/package.json'}")
        record_restart_event("web", ok=proc is not None)
    if target == "bot":
        proc = None
        py = repo / ".venv" / "bin" / "python"
        if py.is_file():
            try:
                proc = subprocess.Popen([str(py), "-m", "app.bot.telegram_bot"], cwd=str(repo), start_new_session=True)
            except OSError:
                proc = None
        print(f"Telegram bot {'started' if proc else 'failed'}")
        record_restart_event("bot", ok=proc is not None)
    if target == "connection":
        from aethos_cli.connection_cli import cmd_connection_repair

        code = cmd_connection_repair()
        record_restart_event("connection", ok=code == 0)
        return code
    record_restart_event(target, ok=ok, detail="restart complete")
    from aethos_cli.cli_status import cmd_status

    return cmd_status()
