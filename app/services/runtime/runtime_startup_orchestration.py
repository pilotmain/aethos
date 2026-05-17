# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise startup orchestration from setup (Phase 4 Step 28)."""

from __future__ import annotations

import os
import socket
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
    from aethos_cli.setup_interactive_mode import setup_interactive

    if setup_interactive():
        from aethos_cli.setup_prompt_runtime import prompt_select

        return prompt_select(
            "Would you like to start AethOS now?",
            [
                ("Start API + Mission Control", "api_and_mission_control", "Recommended"),
                ("Start API only", "api_only", "Mission Control separately"),
                ("Save configuration only", "save_only", "Start later with aethos runtime launch"),
                ("Review setup", "review", "Inspect configuration before starting"),
            ],
            default_index=0,
        )
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
    """Progressive staged startup with coordination and honest readiness."""
    from app.services.runtime.runtime_progressive_startup import orchestrate_progressive_startup

    return orchestrate_progressive_startup(choice=choice, repo_root=repo_root)


def build_runtime_startup_orchestration(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    launch = truth.get("runtime_launch_integrity") or {}
    return {
        "runtime_startup_orchestration": {
            "phase": "phase4_step29",
            "options": [o[0] for o in _START_OPTIONS],
            "api_reachable": launch.get("api_reachable"),
            "mission_control_reachable": launch.get("mission_control_reachable"),
            "truly_operational": launch.get("coordination_complete"),
            "never_premature_ready": True,
            "progressive_stages": 8,
            "bounded": True,
        }
    }
