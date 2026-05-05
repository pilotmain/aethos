"""Execute pluggable skills (Python entrypoints; shell reserved)."""

from __future__ import annotations

import asyncio
import importlib.util
import logging
from pathlib import Path
from typing import Any

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


async def execute_python_skill(skill: SkillManifest, input_data: dict[str, Any]) -> SkillExecutionResult:
    """Load ``skill.entry`` and call ``skill.handler``."""
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
    try:
        if asyncio.iscoroutinefunction(fn):
            out = await fn(**input_data)
        else:
            out = fn(**input_data)
        return SkillExecutionResult(success=True, output=out)
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


__all__ = ["SkillExecutionResult", "execute_python_skill", "execute_shell_skill"]
