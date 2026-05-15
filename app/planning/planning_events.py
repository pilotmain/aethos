# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Planning / reasoning / optimization runtime events + structured logs."""

from __future__ import annotations

from typing import Any

from app.orchestration import orchestration_log
from app.runtime.events.runtime_events import emit_runtime_event


def emit_planning_event(st: dict[str, Any], event: str, **fields: Any) -> None:
    emit_runtime_event(st, event, **fields)
    orchestration_log.append_json_log("planning", event, **fields)
    if event.startswith("reasoning") or "reasoning" in event:
        orchestration_log.append_json_log("reasoning", event, **fields)
    if "optim" in event or "optimization" in event:
        orchestration_log.append_json_log("optimization", event, **fields)
    if "replan" in event or event == "workflow_replanned":
        orchestration_log.append_json_log("replanning", event, **fields)
    if "retry" in event or event == "adaptive_retry_triggered":
        orchestration_log.append_json_log("adaptive_execution", event, **fields)
    if "delegation" in event:
        orchestration_log.append_json_log("delegation_optimization", event, **fields)
