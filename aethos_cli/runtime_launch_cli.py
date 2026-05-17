# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime launch CLI (Phase 4 Step 28)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def cmd_runtime_launch() -> int:
    from app.services.runtime.runtime_launch_orchestration import finalize_first_launch_experience
    from app.services.runtime.runtime_startup_orchestration import orchestrate_startup, prompt_startup_choice
    from aethos_cli.setup_interactive_mode import setup_interactive

    choice = prompt_startup_choice()
    result = orchestrate_startup(choice=choice, repo_root=_repo_root())
    if choice not in ("save_only", "review"):
        result = finalize_first_launch_experience(
            result,
            interactive=setup_interactive(),
            auto_open=choice == "api_and_mission_control",
        )
    else:
        print(result.get("message") or "Launch complete.", file=sys.stderr)
    if os.environ.get("AETHOS_RUNTIME_JSON"):
        print(json.dumps(result, indent=2, default=str)[:12000])
    return 0 if result.get("ok") else 1


def cmd_runtime_startup_status() -> int:
    from app.services.runtime.runtime_startup_visibility import build_runtime_startup_status

    blob = build_runtime_startup_status()
    print(json.dumps(blob, indent=2, default=str)[:12000])
    return 0


def cmd_runtime_launch_experience() -> int:
    from app.services.runtime.runtime_launch_experience import build_runtime_launch_experience

    print(json.dumps(build_runtime_launch_experience(), indent=2, default=str)[:12000])
    return 0


def cmd_runtime_startup_recovery() -> int:
    from app.services.setup.setup_operational_recovery import build_setup_operational_recovery

    blob = build_setup_operational_recovery()
    print(json.dumps(blob, indent=2, default=str)[:12000])
    return 0
