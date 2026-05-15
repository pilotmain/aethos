"""Structured JSON logs for autonomous execution parity."""

from __future__ import annotations

from typing import Any

from app.orchestration.orchestration_log import append_json_log


def log_execution_event(event: str, **fields: Any) -> None:
    append_json_log("execution", event, **fields)


def log_checkpoint_event(event: str, **fields: Any) -> None:
    append_json_log("checkpoints", event, **fields)


def log_retry_event(event: str, **fields: Any) -> None:
    append_json_log("retries", event, **fields)


def log_scheduler_event(event: str, **fields: Any) -> None:
    append_json_log("scheduler", event, **fields)
