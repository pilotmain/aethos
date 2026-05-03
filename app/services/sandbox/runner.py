"""Execution wrappers — Phase 54 MVP delegates to local process unless Docker mode is wired."""

from __future__ import annotations

from typing import Any, Callable

from app.services.sandbox.types import SandboxMode


def run_with_sandbox(mode: SandboxMode, fn: Callable[[], Any]) -> Any:
    """MVP: always invokes ``fn`` directly; future: container/gVisor dispatch."""
    return fn()


__all__ = ["run_with_sandbox"]
