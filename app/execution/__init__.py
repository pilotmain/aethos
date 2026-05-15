"""Autonomous execution parity (OpenClaw Phase 1 — JSON-backed)."""

from app.execution.execution_plan import attach_plan_to_task, create_plan, get_plan

__all__ = ["attach_plan_to_task", "create_plan", "get_plan"]


def __getattr__(name: str):
    if name == "tick_planned_task":
        from app.execution.execution_supervisor import tick_planned_task as tpt

        return tpt
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
