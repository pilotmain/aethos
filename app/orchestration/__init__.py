"""OpenClaw-equivalent orchestration runtime (persistent queues, registry, scheduler)."""

from __future__ import annotations

from typing import Any

from app.orchestration.task_registry import TASK_STATES

__all__ = ["TASK_STATES", "orchestration_boot"]


def __getattr__(name: str) -> Any:
    if name == "orchestration_boot":
        from app.orchestration.orchestrator import orchestration_boot as ob

        return ob
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
