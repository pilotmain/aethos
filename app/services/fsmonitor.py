# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lightweight directory polling for ops-style \"monitor this folder\" flows."""

from __future__ import annotations

import fnmatch
import threading
import time
from pathlib import Path
from typing import Callable

_watch_lock = threading.Lock()
_watchers: dict[str, dict] = {}
_poll_thread: threading.Thread | None = None
_poll_stop = threading.Event()


def _snapshot(path: Path, pattern: str) -> dict[str, float]:
    states: dict[str, float] = {}
    if not path.exists():
        return states
    pat = pattern.strip() or "*"
    try:
        for fp in path.rglob("*"):
            if not fp.is_file():
                continue
            try:
                if not fnmatch.fnmatch(fp.name, pat):
                    continue
                states[str(fp.resolve())] = fp.stat().st_mtime
            except OSError:
                continue
    except OSError:
        pass
    return states


def _poll_loop() -> None:
    while not _poll_stop.is_set():
        time.sleep(2.0)
        now = time.monotonic()
        with _watch_lock:
            ids = list(_watchers.items())
        for wid, w in ids:
            if now >= float(w["expires_at"]):
                with _watch_lock:
                    _watchers.pop(wid, None)
                continue
            path: Path = w["path"]
            pattern = w["pattern"]
            cb: Callable[[str], None] = w["callback"]
            cur = _snapshot(path, pattern)
            last: dict[str, float] = w["last_state"]
            for fp, mtime in cur.items():
                if fp not in last or last[fp] != mtime:
                    try:
                        cb(fp)
                    except Exception:
                        pass
            w["last_state"] = cur


def _ensure_poll_thread() -> None:
    global _poll_thread
    with _watch_lock:
        if _poll_thread is not None and _poll_thread.is_alive():
            return
        _poll_stop.clear()
        _poll_thread = threading.Thread(target=_poll_loop, name="aethos-fsmonitor", daemon=True)
        _poll_thread.start()


def watch(
    path: str,
    pattern: str,
    on_change: Callable[[str], None],
    *,
    duration_seconds: float = 1800.0,
) -> str:
    """
    Register a best-effort poll watcher. Returns watcher id.
    First use starts a daemon poll thread (2s interval).
    """
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(str(p))
    wid = f"{p}:{pattern}:{time.time_ns()}"
    with _watch_lock:
        _watchers[wid] = {
            "path": p,
            "pattern": pattern,
            "callback": on_change,
            "expires_at": time.monotonic() + float(duration_seconds),
            "last_state": _snapshot(p, pattern),
        }
    _ensure_poll_thread()
    return wid


def stop_all() -> None:
    """Testing / shutdown hook."""
    global _poll_thread
    _poll_stop.set()
    with _watch_lock:
        _watchers.clear()
    t = _poll_thread
    if t is not None and t.is_alive():
        t.join(timeout=2.0)
    _poll_thread = None


__all__ = ["watch", "stop_all"]
