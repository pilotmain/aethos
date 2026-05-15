"""FastAPI lifespan hooks for orchestration (after runtime shell)."""

from __future__ import annotations

import logging
import os

from app.runtime.runtime_state import load_runtime_state, save_runtime_state
from app.orchestration.orchestrator import orchestration_boot
from app.orchestration import task_scheduler

_LOG = logging.getLogger(__name__)


def _skip() -> bool:
    if os.environ.get("NEXA_PYTEST") == "1" and os.environ.get("AETHOS_ORCHESTRATION_ENABLE_IN_PYTEST") != "1":
        return True
    return False


def lifespan_orchestration_start() -> None:
    if _skip():
        return
    st = load_runtime_state()
    orchestration_boot(st)
    save_runtime_state(st)


def lifespan_orchestration_stop() -> None:
    if _skip():
        return
    task_scheduler.stop_scheduler_background()
    try:
        st = load_runtime_state()
        sch = st.setdefault("orchestration", {}).setdefault("scheduler", {})
        if isinstance(sch, dict):
            sch["running"] = False
        save_runtime_state(st)
    except Exception as exc:  # noqa: BLE001
        _LOG.debug("orchestration.stop_state_failed %s", exc)
