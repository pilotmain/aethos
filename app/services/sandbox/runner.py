"""Execution wrappers — Phase 54 MVP delegates to local process unless Docker mode is wired."""

from __future__ import annotations

from typing import Any, Callable

from app.services.extensions import get_extension
from app.services.sandbox.types import SandboxMode


def run_with_sandbox(mode: SandboxMode, fn: Callable[[], Any]) -> Any:
    """
    If ``nexa_ext.sandbox`` is installed, delegate to ``run_in_sandbox(mode, fn)`` when present.
    Otherwise invoke ``fn`` in-process (open core).
    """
    mod = get_extension("sandbox")
    if mod is not None and hasattr(mod, "run_in_sandbox"):
        return mod.run_in_sandbox(mode, fn)  # type: ignore[no-any-return]
    return fn()


__all__ = ["run_with_sandbox"]
