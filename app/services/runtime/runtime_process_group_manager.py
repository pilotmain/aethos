# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Process-group coordination for API, workers, and Telegram (Phase 4 Step 25)."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

_PATTERNS = (
    "uvicorn app.main:app",
    "app.bot.telegram_bot",
    "runtime_hydration",
    "hydrate_progressive",
)


def _pkill_pattern(pattern: str, *, sig: int = signal.SIGTERM) -> int:
    flag = "-9" if sig == signal.SIGKILL else "-TERM"
    try:
        out = subprocess.run(
            ["pkill", flag, "-f", pattern],
            capture_output=True,
            timeout=5.0,
        )
        return 0 if out.returncode in (0, 1) else out.returncode
    except (OSError, subprocess.TimeoutExpired):
        return -1


def _kill_pid_group(pid: int, *, sig: int = signal.SIGTERM) -> bool:
    if pid <= 0:
        return False
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, sig)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        try:
            os.kill(pid, sig)
            return True
        except (ProcessLookupError, PermissionError, OSError):
            return False


def terminate_runtime_process_groups(*, force: bool = False) -> dict[str, Any]:
    """Stop API, Telegram, hydration orphans, and release locks."""
    from app.services.mission_control.runtime_ownership_lock import (
        record_process_lifecycle_event,
        release_runtime_ownership_if_owner,
    )
    from app.services.mission_control.runtime_service_registry import build_runtime_service_registry
    from app.services.mission_control.runtime_startup_coordination import release_startup_lock_if_owner
    from app.services.telegram_polling_lock import release_telegram_polling_lock_if_owner

    sig = signal.SIGKILL if force else signal.SIGTERM
    terminated: list[str] = []
    registry = build_runtime_service_registry().get("runtime_services") or {}
    services = registry.get("services") or {}
    for svc_name, rows in services.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            pid = int(row.get("pid") or 0)
            if _kill_pid_group(pid, sig=sig):
                terminated.append(f"{svc_name}:{pid}")

    for pattern in _PATTERNS:
        _pkill_pattern(pattern, sig=sig)

    release_runtime_ownership_if_owner()
    release_telegram_polling_lock_if_owner()
    release_startup_lock_if_owner()
    try:
        from app.services.runtime.runtime_truth_ownership_lock import release_truth_hydration_lock_if_owner

        release_truth_hydration_lock_if_owner()
    except Exception:
        pass

    time.sleep(0.8 if not force else 0.3)
    record_process_lifecycle_event("process_group_stop", detail=f"terminated={len(terminated)}", service="runtime")
    return {
        "ok": True,
        "terminated_pids": terminated,
        "patterns_cleared": list(_PATTERNS),
        "force": force,
        "message": "Runtime process groups coordinated and stopped.",
    }


def restart_runtime_process_groups(*, clean: bool = False) -> dict[str, Any]:
    """Full process-group restart with optional clean shutdown."""
    stop = terminate_runtime_process_groups(force=clean)
    try:
        from aethos_cli.restart_cli import _repo_root, _start_api

        repo_path = _repo_root()
        port = int(os.environ.get("AETHOS_SERVE_PORT") or os.environ.get("NEXA_SERVE_PORT") or "8010")
        from app.services.mission_control.runtime_ownership_lock import try_acquire_runtime_ownership

        try_acquire_runtime_ownership(role="cli", port=port, force=True)
        proc = _start_api(repo_path, reload=not clean)
        started = proc is not None
        return {
            "ok": started,
            "clean": clean,
            "stop": stop,
            "port": port,
            "message": (
                "Runtime coordination recovered and API restarted."
                if started
                else "Processes stopped but API restart failed — check `.venv` and port availability."
            ),
        }
    except Exception:
        return {
            "ok": stop.get("ok"),
            "clean": clean,
            "stop": stop,
            "message": "Runtime process groups stopped. Start API with `aethos restart runtime`.",
        }


def build_process_group_status() -> dict[str, Any]:
    from app.services.mission_control.runtime_service_registry import build_runtime_service_registry

    reg = build_runtime_service_registry().get("runtime_services") or {}
    return {
        "runtime_process_group": {
            "phase": "phase4_step25",
            "api_instance_count": reg.get("api_instance_count"),
            "telegram_instance_count": reg.get("telegram_instance_count"),
            "orphan_prevention": True,
            "commands": ["aethos runtime stop", "aethos runtime restart", "aethos runtime restart --clean"],
            "bounded": True,
        }
    }
