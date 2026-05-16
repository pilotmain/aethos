# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Installer interaction lock metadata (Phase 4 Step 17)."""

from __future__ import annotations

from typing import Any

from aethos_cli.setup_conversational import SETUP_GLOBAL_COMMANDS
from aethos_cli.setup_progress_state import build_progress_status


def build_installer_interaction_lock() -> dict[str, Any]:
    return {
        "installer_interaction_lock": {
            "global_commands_wired": True,
            "global_commands": list(SETUP_GLOBAL_COMMANDS),
            "progress_persistence": "~/.aethos/setup/setup_progress.json",
            "bounded_e2e": True,
            "startup_reliability": True,
            "phase": "phase4_step17",
            "bounded": True,
        },
        "setup_progress_snapshot": build_progress_status(),
    }
