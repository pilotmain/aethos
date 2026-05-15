# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Stale PID cleanup and boot-time runtime reconciliation."""

from __future__ import annotations

import logging
import os
from typing import Any

from app.runtime.runtime_state import (
    load_runtime_state,
    record_recovery_event,
    save_runtime_state,
    utc_now_iso,
)

_LOG = logging.getLogger("aethos.runtime")


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, OverflowError, ValueError):
        return False
    return True


def reconcile_stale_gateway_pid(state: dict[str, Any]) -> dict[str, Any]:
    gw = state.setdefault("gateway", {})
    if not gw.get("running"):
        return state
    pid = gw.get("pid")
    if pid is None:
        return state
    try:
        pidi = int(pid)
    except (TypeError, ValueError):
        record_recovery_event(state, "cleared invalid gateway.pid")
        gw["running"] = False
        gw["pid"] = None
        return state
    if not is_pid_alive(pidi):
        record_recovery_event(state, f"cleared stale gateway pid={pidi}")
        gw["running"] = False
        gw["pid"] = None
    return state


def boot_prepare_runtime_state(*, host: str, port: int) -> dict[str, Any]:
    """
    Load ``aethos.json``, recover stale PIDs, mark gateway running for *this* process.

    Called from FastAPI lifespan startup.
    """
    state = load_runtime_state()
    state = reconcile_stale_gateway_pid(state)
    gw = state.setdefault("gateway", {})
    gw["host"] = str(host or "0.0.0.0")
    gw["port"] = int(port)
    gw["running"] = True
    gw["pid"] = os.getpid()
    state["last_started_at"] = utc_now_iso()
    gw["last_heartbeat"] = utc_now_iso()
    try:
        save_runtime_state(state)
    except Exception as exc:
        _LOG.warning("runtime_recovery.boot_save_failed %s", exc)
    return state
