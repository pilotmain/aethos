"""Periodic autonomy tick — memory hints, operator hooks, telemetry (Phase 39)."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.services.events.envelope import emit_runtime_event
from app.services.logging.logger import get_logger

_log = get_logger("scheduler.heartbeat")


def run_heartbeat_cycle() -> dict[str, Any]:
    """
    Interval job: lightweight; safe to run when DB/API load is low.

    Extend with memory consolidation, dev queue probes, or scheduled missions as needed.
    """
    s = get_settings()
    if not getattr(s, "nexa_heartbeat_enabled", False):
        return {"ok": False, "skipped": "disabled"}

    emit_runtime_event(
        "system.heartbeat",
        payload={
            "interval_seconds": int(getattr(s, "nexa_heartbeat_interval_seconds", 300) or 300),
        },
    )
    try:
        from app.services.agents.long_running import tick_all_registered

        lr = tick_all_registered()
        if lr:
            _log.debug("heartbeat long_running ticks=%s", len(lr))
    except Exception:
        _log.debug("heartbeat long_running tick skipped", exc_info=True)
    if getattr(s, "nexa_autonomous_mode", False) and getattr(s, "nexa_autonomy_execution_enabled", True):
        try:
            from app.core.db import SessionLocal
            from app.services.autonomy.executor import run_autonomy_executor_for_all_pending_users

            with SessionLocal() as db:
                exo = run_autonomy_executor_for_all_pending_users(db)
            if exo.get("users"):
                _log.debug("heartbeat autonomy executor users=%s", exo.get("users"))
        except Exception:
            _log.debug("heartbeat autonomy executor skipped", exc_info=True)
    _log.debug("heartbeat tick")
    return {"ok": True, "event": "system.heartbeat"}


__all__ = ["run_heartbeat_cycle"]
