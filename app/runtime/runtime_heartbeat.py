# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Background heartbeat writing ``gateway.last_heartbeat`` to ``aethos.json``."""

from __future__ import annotations

import logging
import os
import threading

_LOG = logging.getLogger("aethos.runtime")

_stop = threading.Event()
_thread: threading.Thread | None = None


def _tick() -> None:
    from app.runtime.runtime_state import load_runtime_state, save_runtime_state, utc_now_iso

    try:
        st = load_runtime_state()
        gw = st.setdefault("gateway", {})
        gw["last_heartbeat"] = utc_now_iso()
        save_runtime_state(st)
    except Exception as exc:
        _LOG.warning("runtime_heartbeat.tick_failed %s", exc)


def _loop(interval: float) -> None:
    while not _stop.wait(interval):
        _tick()


def start_heartbeat_background(interval_seconds: float | None = None) -> None:
    """Start daemon thread (5–60s interval, default 10s or ``AETHOS_RUNTIME_HEARTBEAT_SECONDS``)."""
    global _thread
    stop_heartbeat_background()
    _stop.clear()
    raw = interval_seconds
    if raw is None:
        try:
            raw = float((os.environ.get("AETHOS_RUNTIME_HEARTBEAT_SECONDS") or "10").strip())
        except ValueError:
            raw = 10.0
    floor = 0.2 if (os.environ.get("AETHOS_RUNTIME_HEARTBEAT_TEST_FAST") or "").strip() == "1" else 5.0
    sec = max(floor, min(60.0, float(raw)))
    t = threading.Thread(target=_loop, args=(sec,), name="aethos-runtime-heartbeat", daemon=True)
    t.start()
    _thread = t


def stop_heartbeat_background() -> None:
    global _thread
    _stop.set()
    if _thread is not None and _thread.is_alive():
        _thread.join(timeout=3.0)
    _thread = None
    _stop.clear()
