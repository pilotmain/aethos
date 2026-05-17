# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Seven-stage progressive startup with live operational feedback."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

PROGRESSIVE_STARTUP_STAGES: tuple[tuple[str, str], ...] = (
    ("coordination", "Initializing runtime coordination"),
    ("environment", "Validating environment integrity"),
    ("api", "Starting API services"),
    ("mission_control", "Starting Mission Control"),
    ("readiness", "Verifying operational readiness"),
    ("visibility", "Establishing runtime visibility"),
    ("workspace", "Preparing operator workspace"),
)


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _api_health(port: int) -> bool:
    if not _port_open(port):
        return False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=3.0) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _startup_status(port: int) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/runtime/startup-status", timeout=3.0) as resp:
            import json

            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return {}


def _db_healthy() -> bool:
    try:
        from app.services.mission_control.runtime_db_coordination import build_database_integrity

        db = build_database_integrity()
        integrity = db.get("database_runtime_integrity") or {}
        return bool(integrity.get("healthy") or integrity.get("schema_ok"))
    except Exception:
        return False


def _ownership_healthy() -> bool:
    try:
        from app.services.mission_control.runtime_ownership_lock import build_runtime_ownership_status

        own = build_runtime_ownership_status().get("runtime_ownership") or {}
        return not own.get("conflict_detected")
    except Exception:
        return True


def build_startup_health_dashboard(
    *,
    api_port: int,
    mc_port: int = 3000,
    api_reachable: bool = False,
    mc_reachable: bool = False,
) -> list[str]:
    db = "healthy" if _db_healthy() else "needs attention"
    api_state = "reachable" if api_reachable else ("starting…" if _port_open(api_port) else "offline")
    mc_state = "reachable" if mc_reachable else ("starting…" if _port_open(mc_port) else "offline")
    hydration = "warming runtime truth" if api_reachable and not mc_reachable else ("ready" if api_reachable else "pending")
    routing = "operational" if api_reachable else "pending"
    return [
        f"API: {api_state}",
        f"Mission Control: {mc_state}",
        f"Database: {db}",
        f"Hydration: {hydration}",
        f"Workers: idle",
        f"Routing: {routing}",
    ]


def _print_stage(index: int, total: int, label: str) -> None:
    from aethos_cli.ui import print_info

    print_info(f"[{index}/{total}] {label}")


def _coordinate_before_start() -> dict[str, Any]:
    try:
        from aethos_cli.setup_supervision_preflight import coordinate_runtime_for_setup, run_setup_supervision_preflight

        pre = run_setup_supervision_preflight()
        if pre.get("any_conflict"):
            return coordinate_runtime_for_setup(auto=True)
        return {"ok": True, "message": "No runtime conflicts detected."}
    except Exception as exc:
        return {"ok": False, "message": str(exc)[:120]}


def orchestrate_progressive_startup(
    *,
    choice: str,
    repo_root: Path | None = None,
    on_stage: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    """Coordinate, launch, verify — with staged calm progress."""
    root = repo_root or Path(__file__).resolve().parents[2]
    port = int(os.environ.get("AETHOS_SERVE_PORT") or os.environ.get("NEXA_SERVE_PORT") or "8010")
    mc_port = 3000
    total = len(PROGRESSIVE_STARTUP_STAGES)

    if choice in ("save_only", "review"):
        return {
            "ok": True,
            "started": False,
            "choice": choice,
            "truly_operational": False,
            "message": "Configuration saved. Start later with `aethos runtime launch`.",
        }

    emit = on_stage or _print_stage
    stages_done: list[str] = []

    emit(1, total, PROGRESSIVE_STARTUP_STAGES[0][1])
    coord = _coordinate_before_start()
    stages_done.append("coordination")

    emit(2, total, PROGRESSIVE_STARTUP_STAGES[1][1])
    env_ok = _db_healthy() and _ownership_healthy()
    stages_done.append("environment")

    py = root / ".venv" / "bin" / "python"
    if not py.is_file():
        py = Path(sys.executable)

    api_proc = None
    mc_proc = None

    emit(3, total, PROGRESSIVE_STARTUP_STAGES[2][1])
    if not _api_health(port):
        try:
            api_proc = subprocess.Popen(
                [str(py), "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port)],
                cwd=str(root),
                start_new_session=True,
            )
        except OSError as exc:
            return {
                "ok": False,
                "started": False,
                "choice": choice,
                "truly_operational": False,
                "message": f"AethOS could not start API yet — {exc}",
                "stages": stages_done,
            }
    stages_done.append("api")

    deadline = time.monotonic() + 45.0
    api_ok = False
    while time.monotonic() < deadline:
        if _api_health(port):
            api_ok = True
            break
        time.sleep(0.8)

    mc_ok = True
    if choice == "api_and_mission_control":
        emit(4, total, PROGRESSIVE_STARTUP_STAGES[3][1])
        web = root / "web"
        if web.joinpath("package.json").is_file() and not _port_open(mc_port):
            try:
                mc_proc = subprocess.Popen(["npm", "run", "dev"], cwd=str(web), start_new_session=True)
            except OSError:
                pass
        mc_deadline = time.monotonic() + 30.0
        while time.monotonic() < mc_deadline:
            if _port_open(mc_port):
                mc_ok = True
                break
            time.sleep(1.0)
        stages_done.append("mission_control")
    else:
        stages_done.append("mission_control_skipped")

    emit(5, total, PROGRESSIVE_STARTUP_STAGES[4][1])
    status_blob = _startup_status(port) if api_ok else {}
    db_ok = _db_healthy()
    own_ok = _ownership_healthy()
    stages_done.append("readiness")

    emit(6, total, PROGRESSIVE_STARTUP_STAGES[5][1])
    from aethos_cli.ui import print_box

    print_box("Operational status", build_startup_health_dashboard(
        api_port=port,
        mc_port=mc_port,
        api_reachable=api_ok,
        mc_reachable=mc_ok,
    ))
    stages_done.append("visibility")

    emit(7, total, PROGRESSIVE_STARTUP_STAGES[6][1])
    stages_done.append("workspace")

    truly = api_ok and (mc_ok or choice == "api_only") and db_ok and own_ok and env_ok
    if not truly and api_ok:
        message = "AethOS is preparing operational services…"
    elif truly:
        message = "AethOS is operational."
    else:
        message = "Runtime coordination needs attention — try `aethos doctor`."

    return {
        "ok": truly or api_ok,
        "started": api_proc is not None or _api_health(port),
        "choice": choice,
        "api_port": port,
        "api_reachable": api_ok,
        "mission_control_reachable": mc_ok,
        "database_healthy": db_ok,
        "ownership_healthy": own_ok,
        "truly_operational": truly,
        "coordination": coord,
        "startup_status": status_blob,
        "stages": stages_done,
        "message": message,
        "pid": api_proc.pid if api_proc else None,
        "mc_pid": mc_proc.pid if mc_proc else None,
    }


__all__ = [
    "PROGRESSIVE_STARTUP_STAGES",
    "build_startup_health_dashboard",
    "orchestrate_progressive_startup",
]
