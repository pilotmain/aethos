# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Structured logs + runtime bus for coordination lifecycle."""

from __future__ import annotations

from typing import Any

from app.orchestration import orchestration_log
from app.runtime.events.runtime_events import emit_runtime_event


def emit_agent_event(st: dict[str, Any], event: str, **fields: Any) -> None:
    emit_runtime_event(st, event, **fields)
    orchestration_log.append_json_log("agents", event, **fields)
    if event.startswith("delegation_"):
        orchestration_log.append_json_log("agent_delegation", event, **fields)
    elif event in ("supervisor_restart",) or "supervisor" in event:
        orchestration_log.append_json_log("runtime_supervision", event, **fields)
    if "loop" in event:
        orchestration_log.append_json_log("autonomous_loops", event, **fields)
