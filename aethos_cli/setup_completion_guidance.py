# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Post-setup guidance and optional Mission Control tour."""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path
from typing import Any

from aethos_cli.setup_interactive_mode import setup_interactive
from aethos_cli.ui import confirm, print_box, print_info, print_success


def _tour_state_path() -> Path:
    return Path.home() / ".aethos" / "mission_control_tour.json"


def mark_guided_tour_requested() -> None:
    path = _tour_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = {"requested": True, "completed": False, "dismissed": False}
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")


def load_tour_state() -> dict[str, Any]:
    path = _tour_state_path()
    if not path.is_file():
        return {"requested": False, "completed": False, "dismissed": False}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"requested": False, "completed": False, "dismissed": False}


def print_what_happens_next(*, operational: bool) -> None:
    if not operational:
        print_box(
            "What happens next",
            [
                "Configuration is saved.",
                "Start services: aethos start",
                "Check health: aethos status",
                "Repair if needed: aethos repair",
                "Docs: docs/ENTERPRISE_SETUP.md",
            ],
        )
        return
    print_box(
        "AethOS is operational",
        [
            "Suggested first actions:",
            "• Open Mission Control  (aethos open)",
            "• Create your first workspace",
            "• Connect a provider",
            "• Configure Telegram or Slack",
            "• Launch your first runtime worker",
            "• Explore Office",
        ],
    )


def prompt_guided_first_run_tour() -> bool:
    if not setup_interactive():
        return False
    if load_tour_state().get("completed") or load_tour_state().get("dismissed"):
        return False
    if confirm("Would you like a guided first-run tour in Mission Control?", default=True):
        mark_guided_tour_requested()
        print_success("Tour will appear when you open Mission Control.")
        return True
    return False


def try_open_mission_control(*, mc_url: str = "http://localhost:3000/mission-control/office") -> bool:
    try:
        import socket

        with socket.create_connection(("127.0.0.1", 3000), timeout=0.5):
            pass
    except OSError:
        print_info("Mission Control is not reachable yet — start with `aethos start`.")
        return False
    try:
        webbrowser.open(mc_url)
        print_info(f"Opened {mc_url}")
        return True
    except Exception:
        print_info(f"Open Mission Control: {mc_url}")
        return False


__all__ = [
    "load_tour_state",
    "mark_guided_tour_requested",
    "print_what_happens_next",
    "prompt_guided_first_run_tour",
    "try_open_mission_control",
]
