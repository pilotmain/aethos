"""Background scheduler loop (poll queues, dispatch with concurrency=1 in Phase 1)."""

from __future__ import annotations

import os
import threading
import time
import logging
from typing import Any

from app.runtime.runtime_state import load_runtime_state, save_runtime_state
from app.execution import execution_log
from app.orchestration import runtime_dispatcher
from app.orchestration import orchestration_log

_LOG = logging.getLogger(__name__)

_INTERVAL_SEC = float(os.environ.get("AETHOS_ORCHESTRATION_TICK_SEC", "10"))
if os.environ.get("AETHOS_ORCHESTRATION_TEST_FAST") == "1":
    _INTERVAL_SEC = 0.05

_lock = threading.Lock()
_thread: threading.Thread | None = None
_stop = threading.Event()


def _skip_background() -> bool:
    if os.environ.get("NEXA_PYTEST") == "1" and os.environ.get("AETHOS_ORCHESTRATION_ENABLE_IN_PYTEST") != "1":
        return True
    return False


def _loop() -> None:
    while not _stop.is_set():
        try:
            with _lock:
                st = load_runtime_state()
                sch = st.setdefault("orchestration", {}).setdefault("scheduler", {})
                if not isinstance(sch, dict):
                    sch = {}
                    st["orchestration"]["scheduler"] = sch
                sch["running"] = True
                sch["ticks"] = int(sch.get("ticks") or 0) + 1
                sch["last_tick"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                sch["last_error"] = None
                res = runtime_dispatcher.dispatch_once(st)
                if res and not res.get("skipped"):
                    orchestration_log.log_orchestration_event(
                        "scheduler_tick",
                        ticks=sch["ticks"],
                        task_id=res.get("task_id"),
                        terminal=res.get("terminal"),
                    )
                    execution_log.log_scheduler_event(
                        "scheduler_tick",
                        ticks=sch["ticks"],
                        task_id=res.get("task_id"),
                        terminal=res.get("terminal"),
                    )
                save_runtime_state(st)
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("orchestration.scheduler_tick_failed %s", exc)
            try:
                st = load_runtime_state()
                sch = st.setdefault("orchestration", {}).setdefault("scheduler", {})
                if isinstance(sch, dict):
                    sch["last_error"] = str(exc)
                save_runtime_state(st)
            except Exception:
                pass
        _stop.wait(_INTERVAL_SEC)


def start_scheduler_background() -> None:
    global _thread
    if _skip_background():
        return
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="aethos-orchestration-scheduler", daemon=True)
    _thread.start()
    orchestration_log.log_orchestration_event("scheduler_started", status="running")


def stop_scheduler_background() -> None:
    global _thread
    _stop.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=5.0)
    _thread = None
    orchestration_log.log_orchestration_event("scheduler_stopped", status="stopped")
