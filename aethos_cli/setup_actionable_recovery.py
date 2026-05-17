# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Actionable recovery prompts during setup (DB lock, API, Mission Control)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from aethos_cli.setup_interactive_mode import setup_interactive
from aethos_cli.ui import print_info, print_success, print_warn


def prompt_db_lock_recovery() -> str:
    """Return: use_existing | restart | retry | later"""
    if not setup_interactive():
        return "later"
    from aethos_cli.setup_prompt_runtime import prompt_select

    return prompt_select(
        "AethOS detected an active runtime using the database. What should I do?",
        [
            ("Coordinate and restart runtime now", "restart", "Stop conflicting processes and retry"),
            ("Use existing runtime", "use_existing", "Skip database init for now"),
            ("Retry database initialization", "retry", "Try ensure_schema again"),
            ("Continue and validate later", "later", "Finish setup; validate afterward"),
        ],
        default_index=4,
    )


def handle_db_lock_recovery(action: str, *, repo_root: Path) -> int:
    action = (action or "later").strip().lower()
    if action == "use_existing":
        print_info("Using existing runtime — database init deferred.")
        return 0
    if action == "later":
        print_info("Database init deferred — run `aethos setup validate` when ready.")
        return 0
    if action == "restart":
        try:
            from aethos_cli.runtime_process_cli import cmd_runtime_restart

            rc = cmd_runtime_restart(clean=True)
            if rc != 0:
                print_warn("Runtime restart returned non-zero — retrying database init anyway.")
        except Exception as exc:
            print_warn(f"Could not restart runtime: {exc}")
        action = "retry"
    if action == "retry":
        from aethos_cli.setup_wizard import run_database_setup

        return run_database_setup()
    return 0


def prompt_service_start(label: str, *, default_yes: bool = True) -> bool:
    if not setup_interactive():
        return False
    from aethos_cli.setup_prompt_runtime import prompt_confirm

    return prompt_confirm(f"{label} now?", default=default_yes)


def try_start_api(*, repo_root: Path, port: int = 8010) -> dict[str, Any]:
    py = repo_root / ".venv" / "bin" / "python"
    if not py.is_file():
        py = Path(sys.executable)
    try:
        proc = subprocess.Popen(
            [str(py), "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port)],
            cwd=str(repo_root),
            start_new_session=True,
        )
        print_success(f"Starting API on port {port} (pid {proc.pid}).")
        return {"ok": True, "pid": proc.pid, "port": port}
    except OSError as exc:
        print_warn(f"Could not start API: {exc}")
        return {"ok": False, "error": str(exc)}


def try_start_mission_control(*, repo_root: Path) -> dict[str, Any]:
    web = repo_root / "web"
    if not (web / "package.json").is_file():
        print_warn("Mission Control web/ directory not found — start manually with `npm run dev` in web/.")
        return {"ok": False, "error": "web_missing"}
    npm = "npm"
    try:
        proc = subprocess.Popen(
            [npm, "run", "dev"],
            cwd=str(web),
            start_new_session=True,
        )
        print_success(f"Starting Mission Control (pid {proc.pid}).")
        return {"ok": True, "pid": proc.pid}
    except OSError as exc:
        print_warn(f"Could not start Mission Control: {exc}")
        return {"ok": False, "error": str(exc)}


__all__ = [
    "handle_db_lock_recovery",
    "prompt_db_lock_recovery",
    "prompt_service_start",
    "try_start_api",
    "try_start_mission_control",
]
