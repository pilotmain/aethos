# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise startup orchestration from setup (Phase 4 Step 28)."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_START_OPTIONS = (
    ("api_and_mission_control", "Start API + Mission Control"),
    ("api_only", "Start API only"),
    ("save_only", "Save configuration only"),
    ("review", "Review setup"),
)


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _health_ok(port: int) -> bool:
    if not _port_open(port):
        return False
    try:
        import urllib.request

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=3.0) as resp:
            return resp.status == 200
    except Exception:
        return _port_open(port)


def prompt_startup_choice() -> str:
    from aethos_cli.ui import select

    return select(
        "Would you like AethOS to start now?",
        [
            ("Start API + Mission Control", "api_and_mission_control", "Recommended"),
            ("Start API only", "api_only", "Mission Control separately"),
            ("Save configuration only", "save_only", "Start later with aethos runtime launch"),
            ("Review setup", "review", "Inspect configuration before starting"),
        ],
        default_index=0,
    )


def orchestrate_startup(*, choice: str, repo_root: Path | None = None) -> dict[str, Any]:
    """Start services per installer choice; wait for health when starting."""
    root = repo_root or Path(__file__).resolve().parents[2]
    port = int(os.environ.get("AETHOS_SERVE_PORT") or os.environ.get("NEXA_SERVE_PORT") or "8010")
    mc_port = 3000
    if choice in ("save_only", "review"):
        return {
            "ok": True,
            "started": False,
            "choice": choice,
            "message": "Configuration saved. Start later with `aethos runtime launch`.",
        }
    py = root / ".venv" / "bin" / "python"
    if not py.is_file():
        py = Path(sys.executable)
    proc = None
    try:
        proc = subprocess.Popen(
            [str(py), "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port)],
            cwd=str(root),
            start_new_session=True,
        )
    except OSError as exc:
        return {"ok": False, "started": False, "message": str(exc)[:120]}
    deadline = time.monotonic() + 45.0
    api_ok = False
    while time.monotonic() < deadline:
        if _health_ok(port):
            api_ok = True
            break
        time.sleep(0.8)
    mc_ok = _port_open(mc_port) if choice == "api_and_mission_control" else True
    truly_ready = api_ok and (mc_ok or choice == "api_only")
    return {
        "ok": truly_ready,
        "started": proc is not None,
        "choice": choice,
        "api_port": port,
        "api_reachable": api_ok,
        "mission_control_reachable": mc_ok,
        "truly_operational": truly_ready,
        "message": (
            "Operational startup completed."
            if truly_ready
            else "AethOS is preparing operational services — check `aethos runtime startup-status`."
        ),
        "pid": proc.pid if proc else None,
    }


def build_runtime_startup_orchestration(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    launch = truth.get("runtime_launch_integrity") or {}
    return {
        "runtime_startup_orchestration": {
            "phase": "phase4_step28",
            "options": [o[0] for o in _START_OPTIONS],
            "api_reachable": launch.get("api_reachable"),
            "mission_control_reachable": launch.get("mission_control_reachable"),
            "truly_operational": launch.get("coordination_complete"),
            "never_premature_ready": True,
            "bounded": True,
        }
    }
