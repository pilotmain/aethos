# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Prevent duplicate truth hydration and governance cycles (Phase 4 Step 25)."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_TRUTH_LOCK = Path.home() / ".aethos" / "runtime" / "truth_hydration.lock"
_LOCK_WAIT_S = 60.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_lock() -> dict[str, Any] | None:
    if not _TRUTH_LOCK.is_file():
        return None
    try:
        blob = json.loads(_TRUTH_LOCK.read_text(encoding="utf-8"))
        return blob if isinstance(blob, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def try_acquire_truth_hydration_lock(*, cycle: str = "hydration") -> bool:
    mypid = os.getpid()
    existing = _read_lock()
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
            _TRUTH_LOCK.unlink(missing_ok=True)
        except OSError:
            return False
    try:
        _TRUTH_LOCK.parent.mkdir(parents=True, exist_ok=True)
        _TRUTH_LOCK.write_text(
            json.dumps(
                {"pid": mypid, "cycle": cycle, "acquired_at": _utc_now(), "monotonic_started": time.monotonic()},
                indent=2,
            ),
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def release_truth_hydration_lock_if_owner() -> None:
    existing = _read_lock()
    if existing and int(existing.get("pid") or -1) == os.getpid():
        try:
            _TRUTH_LOCK.unlink(missing_ok=True)
        except OSError:
            pass


def build_runtime_truth_authority(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    truth = truth or {}
    lock = _read_lock()
    holder = int(lock.get("pid") or 0) if lock else 0
    holder_alive = False
    if holder:
        try:
            os.kill(holder, 0)
            holder_alive = True
        except (ProcessLookupError, PermissionError):
            holder_alive = False
    duplicate_prevented = not holder_alive or holder == os.getpid()
    hydration_locked = holder_alive and holder != os.getpid()
    return {
        "runtime_truth_authority": {
            "phase": "phase4_step25",
            "truth_hydration_locked": hydration_locked,
            "duplicate_hydration_prevented": duplicate_prevented,
            "runtime_truth_authoritative": duplicate_prevented and not hydration_locked,
            "holder_pid": holder if holder_alive else None,
            "cycle": lock.get("cycle") if holder_alive else None,
            "lock_path": str(_TRUTH_LOCK),
            "bounded": True,
        },
        "truth_hydration_locked": hydration_locked,
        "duplicate_hydration_prevented": duplicate_prevented,
        "runtime_truth_authoritative": duplicate_prevented and not hydration_locked,
    }
