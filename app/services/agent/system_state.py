# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 73e — small key/value store for system-wide signals that don't
naturally belong on a per-agent or per-proposal row.

Lives in the existing ``data/agent_audit.db`` (same connection-per-call
pattern as :mod:`app.services.agent.learning` and
:mod:`app.services.agent.activity_tracker`). Two well-known keys are used
in 73e:

* ``last_heartbeat_at`` — bumped on every successful
  :func:`app.services.scheduler.heartbeat.run_heartbeat_cycle` so the
  detailed health endpoint can report a heartbeat-age value the operator
  can act on.
* ``last_auto_revert_at`` — set by
  :mod:`app.services.self_improvement.revert_monitor` whenever it fires
  an automatic revert PR. The 73d auto-merge-on-CI flow checks this
  timestamp and pauses itself for ``NEXA_SELF_IMPROVEMENT_REVERT_COOLDOWN_MINUTES``
  to avoid a revert/un-revert loop. Manual operator merges remain
  unaffected.

All write paths swallow exceptions and log at WARN — recording or
reading state must never break the surrounding hot path.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)


_LAST_HEARTBEAT_KEY = "last_heartbeat_at"
_LAST_AUTO_REVERT_KEY = "last_auto_revert_at"
_PROCESS_STARTED_KEY = "process_started_at"


class SystemStateStore:
    """Tiny ``(key, value, updated_at)`` table sitting next to mistakes."""

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS system_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            settings = get_settings()
            root = Path(getattr(settings, "nexa_data_dir", "") or "data")
            db_path = root / "agent_audit.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        try:
            with self._lock, self._connect() as conn:
                conn.execute(self._SCHEMA)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SystemStateStore._init_db suppressed: %s", exc)

    # --- generic getters / setters --------------------------------------

    def set(self, key: str, value: str) -> None:
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO system_state (key, value, updated_at)
                    VALUES (?, ?, datetime('now'))
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (key, value),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("SystemStateStore.set(%s) suppressed: %s", key, exc)

    def get(self, key: str) -> tuple[str, str] | None:
        """Returns ``(value, updated_at)`` or ``None``."""
        try:
            with self._lock, self._connect() as conn:
                cur = conn.execute(
                    "SELECT value, updated_at FROM system_state WHERE key = ?",
                    (key,),
                )
                row = cur.fetchone()
        except Exception as exc:  # noqa: BLE001
            logger.warning("SystemStateStore.get(%s) suppressed: %s", key, exc)
            return None
        if not row:
            return None
        return (str(row["value"]) if row["value"] is not None else "", str(row["updated_at"]))

    def get_value(self, key: str) -> str | None:
        got = self.get(key)
        return got[0] if got else None

    def get_updated_at(self, key: str) -> str | None:
        got = self.get(key)
        return got[1] if got else None

    # --- well-known: heartbeat ------------------------------------------

    def touch_heartbeat(self) -> None:
        """Bump the cached ``last_heartbeat_at`` timestamp to *now*."""
        self.set(_LAST_HEARTBEAT_KEY, _utc_now_iso())

    def heartbeat_age_seconds(self) -> float | None:
        ts = self.get_updated_at(_LAST_HEARTBEAT_KEY)
        if not ts:
            return None
        return _seconds_since_iso(ts)

    # --- well-known: auto-revert cooldown -------------------------------

    def mark_auto_revert(self, *, proposal_id: str | None = None) -> None:
        """Stamp the most recent auto-revert event.

        Stores the proposal id as the ``value`` so dashboards can show
        which proposal kicked off the cooldown without having to scan
        the proposal table.
        """
        self.set(_LAST_AUTO_REVERT_KEY, str(proposal_id or ""))

    def last_auto_revert_age_seconds(self) -> float | None:
        ts = self.get_updated_at(_LAST_AUTO_REVERT_KEY)
        if not ts:
            return None
        return _seconds_since_iso(ts)

    def in_auto_revert_cooldown(self, cooldown_minutes: int) -> bool:
        """True iff an auto-revert fired within the cooldown window."""
        if cooldown_minutes <= 0:
            return False
        age = self.last_auto_revert_age_seconds()
        if age is None:
            return False
        return age < (float(cooldown_minutes) * 60.0)

    # --- well-known: process start --------------------------------------

    def mark_process_started(self) -> None:
        """Record when this API process came up.

        Called from the FastAPI lifespan. Used by
        :mod:`app.services.self_improvement.revert_monitor` to enforce
        the post-restart grace window — an artificial error spike during
        the seconds after a restart (in-flight requests being killed,
        modules re-importing) must not trigger a revert.
        """
        self.set(_PROCESS_STARTED_KEY, _utc_now_iso())

    def process_age_seconds(self) -> float | None:
        ts = self.get_updated_at(_PROCESS_STARTED_KEY)
        if not ts:
            return None
        return _seconds_since_iso(ts)


# --- helpers --------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _seconds_since_iso(ts: str) -> float:
    """Parse a SQLite-style timestamp; return seconds-since-now or ``inf``."""
    try:
        if "T" in ts:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        return float("inf")
    delta = (datetime.now(timezone.utc) - dt).total_seconds()
    return max(0.0, delta)


# --- module singleton -----------------------------------------------------


_store: SystemStateStore | None = None


def get_system_state() -> SystemStateStore:
    global _store
    if _store is None:
        _store = SystemStateStore()
    return _store


__all__ = [
    "SystemStateStore",
    "get_system_state",
]
