# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Startup hydration serialization lock (Phase 4 Step 18)."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

_HYDRATION_MUTEX = threading.Lock()
_STARTUP_LOCK = Path.home() / ".aethos" / "runtime" / "startup.lock"
_LOCK_WAIT_S = 45.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def startup_lock_path() -> Path:
    return _STARTUP_LOCK


def _read_startup_lock() -> dict[str, Any] | None:
    if not _STARTUP_LOCK.is_file():
        return None
    try:
        blob = json.loads(_STARTUP_LOCK.read_text(encoding="utf-8"))
        return blob if isinstance(blob, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def try_acquire_startup_lock(*, phase: str = "hydration") -> bool:
    mypid = os.getpid()
    existing = _read_startup_lock()
    if existing:
        old = int(existing.get("pid") or -1)
        if old == mypid:
            return True
        started = float(existing.get("monotonic_started") or 0)
        if started and (time.monotonic() - started) < _LOCK_WAIT_S:
            try:
                os.kill(old, 0)
                return False
            except (ProcessLookupError, PermissionError):
                pass
        try:
            _STARTUP_LOCK.unlink(missing_ok=True)
        except OSError:
            return False
    try:
        _STARTUP_LOCK.parent.mkdir(parents=True, exist_ok=True)
        _STARTUP_LOCK.write_text(
            json.dumps(
                {"pid": mypid, "phase": phase, "acquired_at": _utc_now(), "monotonic_started": time.monotonic()},
                indent=2,
            ),
            encoding="utf-8",
        )
        return True
    except OSError as exc:
        logger.warning("startup lock write failed: %s", exc)
        return False


def release_startup_lock_if_owner() -> None:
    existing = _read_startup_lock()
    if existing and int(existing.get("pid") or -1) == os.getpid():
        try:
            _STARTUP_LOCK.unlink(missing_ok=True)
        except OSError:
            pass


def build_startup_lock_status() -> dict[str, Any]:
    lock = _read_startup_lock()
    holder = int(lock.get("pid") or 0) if lock else 0
    holder_alive = False
    if holder:
        try:
            os.kill(holder, 0)
            holder_alive = True
        except (ProcessLookupError, PermissionError):
            holder_alive = False
    return {
        "runtime_startup_lock": {
            "lock_path": str(_STARTUP_LOCK),
            "holder_pid": holder if holder_alive else None,
            "phase": lock.get("phase") if holder_alive else None,
            "this_pid": os.getpid(),
            "serialized_hydration": True,
            "mutex_held": _HYDRATION_MUTEX.locked(),
            "bounded": True,
        }
    }


OWNERSHIP_STARTUP_STATES = (
    "ownership_coordination",
    "database_verification",
    "runtime_recovery",
    "hydration_initialization",
    "office_activation",
    "enterprise_ready",
)


def build_runtime_startup_integrity(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    """Startup discipline truth for Step 25."""
    truth = truth or {}
    lock = build_startup_lock_status().get("runtime_startup_lock") or {}
    from app.services.mission_control.runtime_db_coordination import build_database_integrity

    db = build_database_integrity()
    pct = float((truth.get("runtime_startup_experience") or {}).get("readiness_percent") or 0.4)
    idx = min(len(OWNERSHIP_STARTUP_STATES) - 1, int(pct * (len(OWNERSHIP_STARTUP_STATES) - 1)))
    current = OWNERSHIP_STARTUP_STATES[idx]
    serialized = lock.get("holder_pid") is None or lock.get("holder_pid") == os.getpid()
    score = 0.9 if serialized and (db.get("database_runtime_integrity") or {}).get("ok") else 0.65
    return {
        "runtime_startup_integrity": {
            "phase": "phase4_step25",
            "current_state": current,
            "states": OWNERSHIP_STARTUP_STATES,
            "ownership_before_hydration": serialized,
            "parallel_hydration_prevented": serialized,
            "score": score,
            "bounded": True,
        }
    }


@contextmanager
def serialized_hydration(*, phase: str = "hydration") -> Iterator[bool]:
    """Process-wide mutex + file lock for progressive truth hydration."""
    acquired_file = try_acquire_startup_lock(phase=phase)
    _HYDRATION_MUTEX.acquire()
    try:
        yield acquired_file
    finally:
        _HYDRATION_MUTEX.release()
        if acquired_file:
            release_startup_lock_if_owner()
