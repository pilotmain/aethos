"""Structured JSON lines for tool + workflow events (``tools.log``, ``workflows.log``)."""

from __future__ import annotations

from typing import Any

from app.orchestration import orchestration_log


def log_tool_event(event: str, **fields: Any) -> None:
    orchestration_log.append_json_log("tools", event, **fields)


def log_workflow_event(event: str, **fields: Any) -> None:
    orchestration_log.append_json_log("workflows", event, **fields)
