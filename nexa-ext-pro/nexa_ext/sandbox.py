# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Pro sandbox — stronger isolation than OSS in-process execution."""

from __future__ import annotations

import multiprocessing as mp
import queue
from typing import Any, Callable


def run_in_sandbox(mode: str | object, fn: Callable[[], Any]) -> Any:
    """
    ``mode`` is ``docker`` or ``process`` (matches Nexa :class:`SandboxMode` string values).

    ``docker``: child-process isolation (MVP). Full container image execution can be enabled later.
    ``process``: run inline (same as OSS default).
    """
    raw = getattr(mode, "value", mode)
    m = str(raw or "process").strip().lower()
    if m == "docker":
        return _run_docker(fn)
    if m == "process":
        return fn()
    return fn()


def _run_docker(fn: Callable[[], Any]) -> Any:
    """
    MVP: isolate in a fresh process with timeout (no shared interpreter state).

    Optional Docker image execution can wrap this path when ``cloudpickle`` + Docker CLI exist.
    """
    return _run_child_process(fn)


def _run_child_process(fn: Callable[[], Any]) -> Any:
    q: mp.Queue = mp.Queue(maxsize=1)

    def _target() -> None:
        try:
            q.put(("ok", fn()))
        except Exception as e:  # noqa: BLE001
            q.put(("err", e))

    proc = mp.Process(target=_target, daemon=True)
    proc.start()
    proc.join(timeout=300)
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=5)
        raise TimeoutError("sandbox_process_timeout")
    try:
        kind, payload = q.get_nowait()
    except queue.Empty as e:
        raise RuntimeError("sandbox_empty_result") from e
    if kind == "err":
        raise payload
    return payload


__all__ = ["run_in_sandbox"]
