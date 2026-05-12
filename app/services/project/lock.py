# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Process-local mutexes for checkout coordination (Phase 27).

SQLite atomic UPDATE provides cross-thread/process safety for claim/release;
these locks reduce duplicate attempts within one worker.
"""

from __future__ import annotations

import threading
from typing import Final

_mutex_by_task: Final[dict[str, threading.Lock]] = {}
_registry_lock = threading.Lock()


def lock_for_task(task_id: str) -> threading.Lock:
    with _registry_lock:
        return _mutex_by_task.setdefault(task_id, threading.Lock())


__all__ = ["lock_for_task"]
