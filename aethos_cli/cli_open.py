# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Open Mission Control in the default browser when running."""

from __future__ import annotations

import socket
import sys
import webbrowser


def _mc_reachable(port: int = 3000) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def cmd_open(*, path: str = "/mission-control/office") -> int:
    from aethos_cli.setup_completion_guidance import try_open_mission_control

    url = f"http://localhost:3000{path}"
    if not _mc_reachable():
        print("Mission Control is not reachable yet. Start with: aethos start", file=sys.stderr)
        return 1
    ok = try_open_mission_control(mc_url=url if path.startswith("/mission-control") else f"http://localhost:3000{path}")
    return 0 if ok else 1


__all__ = ["cmd_open"]
