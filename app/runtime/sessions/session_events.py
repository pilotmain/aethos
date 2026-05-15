"""Structured session lifecycle lines for ``~/.aethos/logs/runtime_sessions.log``."""

from __future__ import annotations

from typing import Any

from app.orchestration import orchestration_log


def log_session_event(event: str, **fields: Any) -> None:
    orchestration_log.append_json_log("runtime_sessions", event, **fields)
