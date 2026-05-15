"""Structured ``runtime.log`` audit lines for integrity/cleanup runs."""

from __future__ import annotations

from typing import Any

from app.orchestration import orchestration_log


def log_runtime_audit(event: str, **fields: Any) -> None:
    orchestration_log.append_json_log("runtime", event, **fields)
