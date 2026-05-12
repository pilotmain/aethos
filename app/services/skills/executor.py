# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Execute pluggable skills (Python entrypoints; shell reserved).

Phase 75 added a small "sandbox" layer that the registry calls into before
this module:

* a per-skill **timeout** enforced via :func:`asyncio.wait_for` around the
  handler coroutine (sync handlers are wrapped in ``asyncio.to_thread`` so
  the same timeout applies); and
* a **permission allowlist** check (see
  :func:`assert_permissions_allowed`) that rejects skills whose
  ``manifest.permissions`` aren't a subset of
  ``NEXA_MARKETPLACE_SKILL_PERMISSIONS_ALLOWLIST`` when sandbox mode is on.

True OS-level isolation (Docker / firejail) is deferred to a follow-up.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.skills.loader import SkillManifest

logger = logging.getLogger(__name__)


class SkillExecutionResult:
    __slots__ = ("success", "output", "error", "duration_ms")

    def __init__(
        self,
        *,
        success: bool,
        output: Any,
        error: str | None = None,
        duration_ms: float = 0.0,
    ) -> None:
        self.success = success
        self.output = output
        self.error = error
        self.duration_ms = duration_ms


def _resolve_entry_path(skill: SkillManifest) -> Path:
    p = Path(skill.entry)
    if p.is_absolute():
        return p
    return (skill.base_dir / p).resolve()


def _sandbox_enabled() -> bool:
    return bool(getattr(get_settings(), "nexa_marketplace_sandbox_mode", True))


def _skill_timeout_seconds() -> float:
    """Phase 75 — resolve the per-skill timeout. ``0`` disables (no wait_for)."""
    raw = getattr(get_settings(), "nexa_marketplace_skill_timeout_seconds", 30)
    try:
        return float(raw if raw is not None else 30)
    except (TypeError, ValueError):
        return 30.0


def _permissions_allowlist() -> set[str]:
    raw = (
        getattr(get_settings(), "nexa_marketplace_skill_permissions_allowlist", "")
        or ""
    )
    return {p.strip().lower() for p in str(raw).split(",") if p.strip()}


def assert_permissions_allowed(skill: SkillManifest) -> str | None:
    """Phase 75 — return ``None`` if the skill may execute, else a deny reason.

    Sandbox-mode-off short-circuits to ``None`` so trusted built-in handlers
    keep running unchanged. When sandbox-mode is on, the manifest's
    ``permissions`` must be a subset of the operator's allowlist; the first
    permission outside the allowlist is reported in the deny reason.
    """
    if not _sandbox_enabled():
        return None
    if not skill.permissions:
        return None
    allow = _permissions_allowlist()
    blocked = [p for p in skill.permissions if p not in allow]
    if not blocked:
        return None
    return (
        f"permission_not_allowed: skill {skill.name!r} requested {sorted(blocked)} "
        f"but the operator allowlist is {sorted(allow) or '[]'}. "
        "Set NEXA_MARKETPLACE_SKILL_PERMISSIONS_ALLOWLIST to opt in."
    )


async def execute_python_skill(skill: SkillManifest, input_data: dict[str, Any]) -> SkillExecutionResult:
    """Load ``skill.entry`` and call ``skill.handler``.

    Phase 75 wraps the handler call in :func:`asyncio.wait_for` when
    ``NEXA_MARKETPLACE_SANDBOX_MODE=true`` and a non-zero
    ``NEXA_MARKETPLACE_SKILL_TIMEOUT_SECONDS`` is configured. A
    :class:`asyncio.TimeoutError` is reported as a structured failure
    rather than propagating up the call stack.
    """
    path = _resolve_entry_path(skill)
    if not path.is_file():
        return SkillExecutionResult(success=False, output=None, error=f"Skill entry not found: {path}")
    mod_name = f"nexa_skill_{skill.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        return SkillExecutionResult(success=False, output=None, error="Could not load skill module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, skill.handler, None)
    if not callable(fn):
        return SkillExecutionResult(
            success=False,
            output=None,
            error=f"Handler {skill.handler!r} not callable on {path}",
        )

    async def _invoke() -> Any:
        if asyncio.iscoroutinefunction(fn):
            return await fn(**input_data)
        return await asyncio.to_thread(lambda: fn(**input_data))

    timeout_s = _skill_timeout_seconds() if _sandbox_enabled() else 0.0
    try:
        if timeout_s > 0:
            out = await asyncio.wait_for(_invoke(), timeout=timeout_s)
        else:
            out = await _invoke()
        return SkillExecutionResult(success=True, output=out)
    except asyncio.TimeoutError:
        logger.warning(
            "skill python execution timed out name=%s timeout_s=%s",
            skill.name,
            timeout_s,
        )
        return SkillExecutionResult(
            success=False,
            output=None,
            error=f"timeout_exceeded:{timeout_s}s",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("skill python execution failed name=%s", skill.name)
        return SkillExecutionResult(success=False, output=None, error=str(exc))


async def execute_shell_skill(skill: SkillManifest, input_data: dict[str, Any]) -> SkillExecutionResult:
    _ = skill, input_data
    return SkillExecutionResult(
        success=False,
        output=None,
        error="shell execution type not implemented (Phase 6.1)",
    )


__all__ = [
    "SkillExecutionResult",
    "assert_permissions_allowed",
    "execute_python_skill",
    "execute_shell_skill",
]
