"""Host-local worker control files (pause / drain)."""

from __future__ import annotations

from pathlib import Path

from app.services.handoff_paths import PROJECT_ROOT

RUNTIME = Path(PROJECT_ROOT) / ".runtime"
PAUSE_FLAG = RUNTIME / "dev_worker_paused"
STOP_AFTER_FLAG = RUNTIME / "dev_worker_stop_after_current"


def is_worker_paused() -> bool:
    return PAUSE_FLAG.is_file()


def is_stop_after_current() -> bool:
    return STOP_AFTER_FLAG.is_file()


def set_worker_paused() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    PAUSE_FLAG.write_text("1\n", encoding="utf-8")


def clear_worker_paused() -> None:
    try:
        PAUSE_FLAG.unlink()
    except OSError:
        pass


def set_stop_after_current() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    STOP_AFTER_FLAG.write_text("1\n", encoding="utf-8")


def clear_stop_after_current() -> None:
    try:
        STOP_AFTER_FLAG.unlink()
    except OSError:
        pass
