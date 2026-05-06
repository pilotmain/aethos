"""
Single-process Telegram long polling (``getUpdates``).

Only one process may poll per bot token. Embedded API polling and the standalone
``python -m app.bot.telegram_bot`` process coordinate via a PID file in the temp dir.
"""

from __future__ import annotations

import atexit
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCK_NAME = "aethos_telegram_bot.lock"
_registered_release = False


def telegram_polling_lock_path() -> Path:
    return Path(tempfile.gettempdir()) / _LOCK_NAME


def _release_lock_if_owner(path: Path, owner_pid: int) -> None:
    try:
        if not path.exists():
            return
        cur = path.read_text(encoding="utf-8").strip().split()
        if cur and int(cur[0]) == owner_pid:
            path.unlink(missing_ok=True)
    except Exception:
        pass


def try_acquire_telegram_polling_lock() -> bool:
    """
    Attempt to become the sole Telegram polling owner for this machine.

    Returns True if this process wrote the lock (or already owns it).
    Returns False if another live process holds the lock.
    """
    path = telegram_polling_lock_path()
    mypid = os.getpid()

    if path.exists():
        try:
            raw = path.read_text(encoding="utf-8").strip().split()
            old = int(raw[0]) if raw else -1
        except Exception:
            path.unlink(missing_ok=True)
            return try_acquire_telegram_polling_lock()

        if old == mypid:
            return True
        try:
            os.kill(old, 0)
        except ProcessLookupError:
            path.unlink(missing_ok=True)
            return _write_telegram_polling_lock(path, mypid)
        except PermissionError:
            logger.warning("cannot inspect telegram polling lock holder pid=%s", old)
            return False
        logger.info("telegram polling lock held by pid=%s (this pid=%s)", old, mypid)
        return False

    return _write_telegram_polling_lock(path, mypid)


def _write_telegram_polling_lock(path: Path, mypid: int) -> bool:
    """Write lock file and register atexit cleanup (once)."""
    global _registered_release
    try:
        path.write_text(f"{mypid}\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("telegram polling lock write failed: %s", exc)
        return False

    if not _registered_release:
        atexit.register(_release_lock_if_owner, path, mypid)
        _registered_release = True
    return True


def release_telegram_polling_lock_if_owner() -> None:
    """Explicit release (e.g. tests). Safe to call multiple times."""
    _release_lock_if_owner(telegram_polling_lock_path(), os.getpid())
