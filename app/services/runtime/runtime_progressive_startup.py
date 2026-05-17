# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Eight-stage progressive startup with live operational feedback."""

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

from app.services.runtime.runtime_launch_orchestration import (
    UNIFIED_LAUNCH_STAGES,
    build_service_visibility_checklist,
    build_startup_recovery_copy,
    build_warmup_awareness_payload,
    derive_operator_readiness_state,
    print_unified_launch_header,
)

PROGRESSIVE_STARTUP_STAGES = UNIFIED_LAUNCH_STAGES


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
        from app.services.runtime.runtime_health_authority import build_canonical_runtime_health

        return bool(build_canonical_runtime_health()["runtime_health_authority"].get("ownership_valid"))
    except Exception:
        return True


def build_startup_health_dashboard(
    *,
    api_port: int,
    mc_port: int = 3000,
    api_reachable: bool = False,
    mc_reachable: bool = False,
) -> list[str]:
    return build_service_visibility_checklist(
        api_reachable=api_reachable,
        mc_reachable=mc_reachable,
        db_healthy=_db_healthy(),
        hydration_partial=api_reachable and not mc_reachable,
        routing_operational=api_reachable,
    )


def _print_stage(index: int, total: int, label: str) -> None:
    from aethos_cli.ui import print_info

    print_info(f"[{index}/{total}] {label}")


def _coordinate_before_start() -> dict[str, Any]:
    try:
        from app.services.runtime.runtime_health_authority import build_canonical_runtime_health, is_stale_runtime_session
        from aethos_cli.setup_supervision_preflight import coordinate_runtime_for_setup, run_setup_supervision_preflight

        ha = build_canonical_runtime_health()["runtime_health_authority"]
        if ha.get("operational"):
            return {"ok": True, "message": "Existing operational runtime detected."}
        pre = run_setup_supervision_preflight()
        if pre.get("needs_recovery") or is_stale_runtime_session():
            from aethos_cli.ui import print_info

            print_info("AethOS detected an older runtime session. Coordinating recovery…")
            return coordinate_runtime_for_setup(auto=True)
        return {"ok": True, "message": "No runtime conflicts detected."}
    except Exception as exc:
        return {"ok": False, "message": build_startup_recovery_copy(issue=str(exc)[:120])}


def _hydration_partial(status_blob: dict[str, Any]) -> bool:
    readiness = status_blob.get("runtime_readiness") or {}
    if readiness.get("ready") is False:
        return True
    exp = status_blob.get("runtime_startup_experience") or {}
    if exp.get("partial_mode"):
        return True
    pct = float(exp.get("readiness_percent") or 1.0)
    return pct < 0.85


def orchestrate_progressive_startup(
    *,
    choice: str,
    repo_root: Path | None = None,
    on_stage: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    """Coordinate, launch, verify — one orchestrated operational flow."""
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
            "message": "Configuration saved. Start later with `aethos start`.",
        }

    print_unified_launch_header()
    emit = on_stage or _print_stage
    stages_done: list[str] = []

    emit(1, total, PROGRESSIVE_STARTUP_STAGES[0][1])
    coord = _coordinate_before_start()
    if not coord.get("ok"):
        return {
            "ok": False,
            "started": False,
            "choice": choice,
            "truly_operational": False,
            "message": build_startup_recovery_copy(issue=str(coord.get("message") or "")),
            "stages": stages_done,
            "coordination": coord,
        }
    stages_done.append("coordination")

    emit(2, total, PROGRESSIVE_STARTUP_STAGES[1][1])
    db_ok = _db_healthy()
    stages_done.append("database")

    emit(3, total, PROGRESSIVE_STARTUP_STAGES[2][1])
    own_ok = _ownership_healthy()
    env_ok = db_ok and own_ok
    stages_done.append("authority")

    py = root / ".venv" / "bin" / "python"
    if not py.is_file():
        py = Path(sys.executable)

    api_proc = None
    mc_proc = None

    emit(4, total, PROGRESSIVE_STARTUP_STAGES[3][1])
    if not _api_health(port):
        try:
            from app.services.mission_control.runtime_ownership_lock import try_acquire_runtime_ownership

            try_acquire_runtime_ownership(role="cli", port=port, force=True)
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
                "message": build_startup_recovery_copy(issue=str(exc)),
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
        emit(5, total, PROGRESSIVE_STARTUP_STAGES[4][1])
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

    emit(6, total, PROGRESSIVE_STARTUP_STAGES[5][1])
    status_blob: dict[str, Any] = {}
    warmup_deadline = time.monotonic() + 20.0
    while time.monotonic() < warmup_deadline:
        status_blob = _startup_status(port) if api_ok else {}
        if api_ok and not _hydration_partial(status_blob):
            break
        time.sleep(1.0)
    hydration_partial = _hydration_partial(status_blob) if api_ok else True
    stages_done.append("warmup")

    emit(7, total, PROGRESSIVE_STARTUP_STAGES[6][1])
    try:
        from app.services.setup.first_run_operator_onboarding import build_first_run_onboarding_prompt

        build_first_run_onboarding_prompt()
    except Exception:
        pass
    stages_done.append("workspace")

    emit(8, total, PROGRESSIVE_STARTUP_STAGES[7][1])
    from app.services.runtime.runtime_health_authority import build_canonical_runtime_health

    health = build_canonical_runtime_health(api_port=port)
    ha = health["runtime_health_authority"]
    db_ok = bool(ha.get("database_healthy"))
    own_ok = bool(ha.get("ownership_valid"))
    mc_ok = bool(ha.get("mission_control_reachable")) if choice == "api_and_mission_control" else mc_ok
    api_ok = bool(ha.get("api_reachable")) or api_ok
    hydration_partial = not bool(ha.get("hydration_active"))
    stages_done.append("readiness")

    visibility = build_startup_health_dashboard(
        api_port=port,
        mc_port=mc_port,
        api_reachable=api_ok,
        mc_reachable=mc_ok,
    )
    readiness_state = str(ha.get("readiness_state") or derive_operator_readiness_state(
        api_reachable=api_ok,
        mc_reachable=mc_ok,
        db_healthy=db_ok,
        ownership_healthy=own_ok,
        hydration_partial=hydration_partial,
    ))
    truly = bool(ha.get("operational")) and (mc_ok or choice == "api_only")
    if not truly and api_ok:
        message = "AethOS is preparing operational services…"
    elif truly:
        message = "AethOS is operational."
    elif bool(ha.get("stale_session")):
        message = "AethOS detected an incomplete or stale runtime session."
    else:
        message = build_startup_recovery_copy()

    warmup = build_warmup_awareness_payload(
        api_reachable=api_ok,
        mc_reachable=mc_ok,
        hydration_partial=hydration_partial,
        readiness_percent=float((status_blob.get("runtime_startup_experience") or {}).get("readiness_percent") or 0.5),
        current_stage_id="readiness" if truly else "warmup",
    )

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
        "readiness_state": readiness_state,
        "hydration_partial": hydration_partial,
        "coordination": coord,
        "startup_status": status_blob,
        "warmup_awareness": warmup,
        "stages": stages_done,
        "visibility": visibility,
        "message": message,
        "mission_control_url": "http://localhost:3000/mission-control/office",
        "pid": api_proc.pid if api_proc else None,
        "mc_pid": mc_proc.pid if mc_proc else None,
    }


__all__ = [
    "PROGRESSIVE_STARTUP_STAGES",
    "build_startup_health_dashboard",
    "orchestrate_progressive_startup",
]
