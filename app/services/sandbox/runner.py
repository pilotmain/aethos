"""Execution wrappers — Phase 54 MVP delegates to local process unless Docker mode is wired."""

from __future__ import annotations

from typing import Any, Callable

from app.services.extensions import get_extension
from app.services.licensing.features import FEATURE_SANDBOX_ADVANCED, has_pro_feature
from app.services.sandbox.types import SandboxMode


def run_with_sandbox(mode: SandboxMode, fn: Callable[[], Any]) -> Any:
    """
    If ``nexa_ext.sandbox`` is installed **and** the license grants ``sandbox_advanced``,
    delegate to ``run_in_sandbox(mode, fn)``. Otherwise invoke ``fn`` in-process (OSS).
    """
    mod = get_extension("sandbox")
    if (
        mod is not None
        and hasattr(mod, "run_in_sandbox")
        and has_pro_feature(FEATURE_SANDBOX_ADVANCED)
    ):
        return mod.run_in_sandbox(mode, fn)  # type: ignore[no-any-return]
    return fn()


__all__ = ["run_with_sandbox"]
