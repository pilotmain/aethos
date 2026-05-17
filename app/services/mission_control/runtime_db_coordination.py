# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""SQLite coordination — busy timeout, retries, health (Phase 4 Step 18)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.db import engine, get_database_url

logger = logging.getLogger(__name__)

T = TypeVar("T")

_DEFAULT_RETRIES = 5
_DEFAULT_BACKOFF_S = 0.15

_db_lock_state: dict[str, Any] = {
    "db_lock_waiting": False,
    "db_lock_wait_ms": 0,
    "db_retry_count": 0,
    "db_owner_hint": None,
    "db_last_error": None,
}


def get_db_lock_state() -> dict[str, Any]:
    return dict(_db_lock_state)


def _record_lock_wait(*, wait_ms: float, retry: int, error: str | None = None) -> None:
    _db_lock_state["db_lock_waiting"] = True
    _db_lock_state["db_lock_wait_ms"] = round(wait_ms, 2)
    _db_lock_state["db_retry_count"] = retry
    if error:
        _db_lock_state["db_last_error"] = error[:200]
    try:
        from app.services.mission_control.runtime_ownership_lock import build_runtime_ownership_status

        own = build_runtime_ownership_status().get("runtime_ownership") or {}
        _db_lock_state["db_owner_hint"] = own.get("holder_pid") or own.get("telegram_polling_pid")
    except Exception:
        pass


def clear_db_lock_state() -> None:
    _db_lock_state.update(
        {
            "db_lock_waiting": False,
            "db_lock_wait_ms": 0,
            "db_retry_count": 0,
            "db_owner_hint": None,
            "db_last_error": None,
        }
    )


def apply_sqlite_pragmas() -> None:
    """Best-effort WAL + busy_timeout for file-backed SQLite."""
    url = (get_database_url() or "").lower()
    if not url.startswith("sqlite"):
        return
    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA busy_timeout=30000"))
            conn.commit()
    except Exception as exc:
        logger.debug("sqlite pragma apply skipped: %s", exc)


def sqlite_retry(
    fn: Callable[[], T],
    *,
    max_attempts: int = _DEFAULT_RETRIES,
    backoff_s: float = _DEFAULT_BACKOFF_S,
) -> T:
    """Retry on SQLite database is locked / busy."""
    last: Exception | None = None
    t0 = time.monotonic()
    for attempt in range(max_attempts):
        try:
            out = fn()
            clear_db_lock_state()
            return out
        except OperationalError as exc:
            msg = str(exc).lower()
            if "locked" not in msg and "busy" not in msg:
                raise
            last = exc
            wait_ms = (time.monotonic() - t0) * 1000.0
            _record_lock_wait(wait_ms=wait_ms, retry=attempt + 1, error=str(exc))
            if attempt + 1 >= max_attempts:
                break
            time.sleep(backoff_s * (attempt + 1))
    assert last is not None
    logger.warning(
        "AethOS SQLite coordination exhausted retries — run `aethos restart runtime` if this persists: %s",
        str(last)[:120],
    )
    raise last


def build_runtime_db_health() -> dict[str, Any]:
    url = get_database_url()
    is_sqlite = url.lower().startswith("sqlite")
    locked_errors = 0
    ok = False
    detail = ""
    try:

        def _probe() -> None:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

        if is_sqlite:
            apply_sqlite_pragmas()
            sqlite_retry(_probe)
        else:
            _probe()
        ok = True
        detail = "connected"
    except OperationalError as exc:
        locked_errors = 1 if "locked" in str(exc).lower() else 0
        detail = str(exc)[:160]
    except Exception as exc:
        detail = str(exc)[:160]

    lock_state = get_db_lock_state()
    return {
        "runtime_db_health": {
            "ok": ok,
            "backend": "sqlite" if is_sqlite else "server",
            "database_url_redacted": url.split("///")[-1][:80] if is_sqlite else "configured",
            "wal_enabled": is_sqlite,
            "busy_timeout_ms": 30000 if is_sqlite else None,
            "recent_lock_errors": locked_errors,
            "detail": detail,
            "retry_policy": f"{_DEFAULT_RETRIES} attempts, backoff {_DEFAULT_BACKOFF_S}s",
            **lock_state,
            "bounded": True,
        }
    }


def ensure_schema_with_recovery() -> dict[str, Any]:
    """Run ensure_schema with retries; return calm status for startup."""
    from app.core.db import ensure_schema

    try:
        ensure_schema()
        clear_db_lock_state()
        return {"ok": True, "message": "schema ready"}
    except OperationalError as exc:
        _record_lock_wait(wait_ms=float(_db_lock_state.get("db_lock_wait_ms") or 0), retry=_DEFAULT_RETRIES, error=str(exc))
        return {
            "ok": False,
            "message": "AethOS database schema initialization is waiting on SQLite coordination. "
            "Stop duplicate API processes and run `aethos restart runtime`.",
            **get_db_lock_state(),
        }
