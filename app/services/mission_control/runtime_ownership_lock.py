# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime process ownership lock (Phase 4 Step 18)."""

from __future__ import annotations

import atexit
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_RUNTIME_DIR = Path.home() / ".aethos" / "runtime"
_OWNERSHIP_FILE = _RUNTIME_DIR / "ownership.lock"
_LIFECYCLE_FILE = _RUNTIME_DIR / "process_lifecycle.json"
_registered_release = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def runtime_dir() -> Path:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return _RUNTIME_DIR


def ownership_lock_path() -> Path:
    return _OWNERSHIP_FILE


def _read_lock(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if raw.startswith("{"):
            return json.loads(raw)
        parts = raw.split()
        return {"pid": int(parts[0]), "role": parts[1] if len(parts) > 1 else "api"}
    except Exception:
        return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _write_lock(path: Path, payload: dict[str, Any]) -> bool:
    global _registered_release
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("runtime ownership lock write failed: %s", exc)
        return False
    mypid = os.getpid()
    if not _registered_release:
        atexit.register(release_runtime_ownership_if_owner)
        _registered_release = True
    return True


def try_acquire_runtime_ownership(
    *,
    role: str = "api",
    port: int | None = None,
    force: bool = False,
) -> bool:
    """Acquire exclusive runtime ownership for this machine (api/cli). Observer never acquires."""
    from app.services.mission_control.runtime_uvicorn_process import detect_uvicorn_process_kind

    if detect_uvicorn_process_kind() == "reloader_parent":
        return False
    if role == "observer":
        return False
    path = ownership_lock_path()
    mypid = os.getpid()
    existing = _read_lock(path)
    if existing:
        old = int(existing.get("pid") or -1)
        if old == mypid:
            return True
        if _pid_alive(old) and not force:
            logger.info("runtime ownership held by pid=%s role=%s", old, existing.get("role"))
            return False
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    from app.services.mission_control.runtime_uvicorn_process import detect_uvicorn_process_kind

    payload = {
        "pid": mypid,
        "role": role,
        "port": port,
        "acquired_at": _utc_now(),
        "uvicorn_kind": detect_uvicorn_process_kind(),
    }
    return _write_lock(path, payload)


def release_runtime_ownership_if_owner() -> None:
    path = ownership_lock_path()
    existing = _read_lock(path)
    if not existing:
        return
    if int(existing.get("pid") or -1) == os.getpid():
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def takeover_runtime_ownership(*, role: str = "cli", port: int | None = None) -> bool:
    """Force ownership — used by `aethos runtime takeover`."""
    release_runtime_ownership_if_owner()
    path = ownership_lock_path()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    return try_acquire_runtime_ownership(role=role, port=port, force=True)


def build_runtime_ownership_status() -> dict[str, Any]:
    from app.services.telegram_polling_lock import telegram_polling_lock_path

    path = ownership_lock_path()
    lock = _read_lock(path)
    holder_pid = int(lock.get("pid") or 0) if lock else None
    holder_alive = _pid_alive(holder_pid) if holder_pid else False
    mypid = os.getpid()
    i_own = holder_pid == mypid and holder_alive

    tg_path = telegram_polling_lock_path()
    tg_pid = 0
    if tg_path.is_file():
        try:
            tg_pid = int(tg_path.read_text(encoding="utf-8").strip().split()[0])
        except Exception:
            tg_pid = 0
    tg_alive = _pid_alive(tg_pid) if tg_pid else False

    duplicate_risk = bool(holder_alive and tg_alive and holder_pid != tg_pid)
    polling_available = (not tg_alive) or tg_pid == mypid

    lifecycle = load_process_lifecycle()
    return {
        "runtime_ownership": {
            "lock_path": str(path),
            "holder_pid": holder_pid if holder_alive else None,
            "holder_role": lock.get("role") if holder_alive else None,
            "holder_port": lock.get("port") if holder_alive else None,
            "this_pid": mypid,
            "this_process_owns": i_own,
            "observer_mode": not i_own and not holder_alive,
            "duplicate_ownership_risk": duplicate_risk,
            "telegram_polling_pid": tg_pid if tg_alive else None,
            "telegram_polling_available": polling_available,
            "embedded_bot_safe": polling_available or i_own,
            "phase": "phase4_step19",
            "stale_owner": bool(lock and not holder_alive),
            "bounded": True,
        },
        "process_lifecycle": lifecycle,
    }


def format_runtime_ownership_summary() -> str:
    """Human-readable summary for CLI and doctor."""
    from app.services.mission_control.runtime_db_coordination import build_runtime_db_health
    from app.services.mission_control.telegram_ownership_ux import build_telegram_ownership_status

    st = build_runtime_ownership_status()["runtime_ownership"]
    db = build_runtime_db_health()["runtime_db_health"]
    tg = build_telegram_ownership_status()["telegram_ownership"]
    owner = "active" if st.get("this_process_owns") else ("stale" if st.get("stale_owner") else "none")
    lines = [
        f"Runtime owner: {owner}",
        f"PID: {st.get('holder_pid') or st.get('this_pid')}",
        f"Mode: {st.get('holder_role') or 'observer'} runtime",
        f"Telegram: {tg.get('mode', 'unknown')}",
        f"SQLite: {'WAL healthy' if db.get('ok') else db.get('detail', 'degraded')}",
        f"Next: {'aethos status' if owner == 'active' else 'aethos runtime takeover --yes'}",
    ]
    return "\n".join(lines)


def load_process_lifecycle() -> dict[str, Any]:
    path = _LIFECYCLE_FILE
    if not path.is_file():
        return {"events": [], "services": {}}
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
        return blob if isinstance(blob, dict) else {"events": [], "services": {}}
    except (OSError, json.JSONDecodeError):
        return {"events": [], "services": {}}


def record_process_lifecycle_event(event: str, *, detail: str | None = None, service: str | None = None) -> None:
    blob = load_process_lifecycle()
    events = list(blob.get("events") or [])
    events.append({"at": _utc_now(), "event": event, "detail": detail, "service": service, "pid": os.getpid()})
    blob["events"] = events[-48:]
    if service:
        services = dict(blob.get("services") or {})
        services[service] = {"last_event": event, "at": _utc_now(), "pid": os.getpid()}
        blob["services"] = services
    try:
        _LIFECYCLE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LIFECYCLE_FILE.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    except OSError:
        pass
