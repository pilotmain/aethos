"""
Phase 6 pluggable skill registry (YAML manifests + Python handlers).

Coexists with :mod:`app.services.skills.registry` (Phase 22 user JSON skills).
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT, get_settings
from app.services.skills.executor import (
    SkillExecutionResult,
    assert_permissions_allowed,
    execute_python_skill,
    execute_shell_skill,
)
from app.services.skills.loader import SkillManifest, load_skill_manifest

logger = logging.getLogger(__name__)


class PluginSkillRegistry:
    """In-memory registry of :class:`SkillManifest` entries."""

    _instance: PluginSkillRegistry | None = None

    def __new__(cls) -> PluginSkillRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._skills = {}
        return cls._instance

    def __init__(self) -> None:
        self._skills: dict[str, SkillManifest]

    def register(self, skill: SkillManifest) -> None:
        self._skills[skill.name] = skill
        logger.info("Registered plugin skill %s v%s", skill.name, skill.version)

    def unregister_skill(self, name: str) -> bool:
        nm = (name or "").strip()
        if nm in self._skills:
            del self._skills[nm]
            logger.info("Unregistered plugin skill %s", nm)
            return True
        return False

    def get_skill(self, name: str) -> SkillManifest | None:
        return self._skills.get(name.strip())

    def list_skills(self, tag: str | None = None) -> list[SkillManifest]:
        out = list(self._skills.values())
        if tag:
            t = tag.strip().lower()
            out = [s for s in out if t in [x.lower() for x in s.tags]]
        return sorted(out, key=lambda s: s.name)

    def discover_skill(self, task: str) -> SkillManifest | None:
        """Reserved for embedding / catalog matching (Phase 6.2)."""
        _ = task
        return None

    async def install_skill(self, name: str, source: str) -> SkillManifest | None:
        src = (source or "").strip()
        if src == "clawhub":
            return await self._install_from_clawhub(name)
        if src.startswith("file://"):
            return await self._install_from_file(src[7:])
        if src.startswith("http://") or src.startswith("https://"):
            return await self._install_from_url(src)
        logger.error("Unknown skill source: %s", source)
        return None

    async def _install_from_clawhub(self, name: str) -> SkillManifest | None:
        from app.services.skills.installer import SkillInstaller

        inst = SkillInstaller()
        ok, msg, skill_key = await inst.install(name, "latest", force=False)
        if not ok or not skill_key:
            logger.warning("ClawHub install failed: %s (%s)", name, msg)
            return None
        return self.get_skill(skill_key)

    async def ensure_dependencies(self, dependencies: list[str]) -> None:
        await self._install_dependencies(dependencies)

    async def _install_from_file(self, path: str) -> SkillManifest | None:
        p = Path(path).expanduser().resolve()
        if not p.is_file():
            logger.error("Skill manifest not found: %s", p)
            return None
        try:
            skill = load_skill_manifest(p)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to parse skill manifest: %s", exc)
            return None
        await self._install_dependencies(skill.dependencies)
        self.register(skill)
        return skill

    async def _install_from_url(self, url: str) -> SkillManifest | None:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.get(url)
                r.raise_for_status()
                text = r.text
        except Exception as exc:  # noqa: BLE001
            logger.error("Skill URL fetch failed: %s", exc)
            return None
        dest = default_plugin_skills_dir() / "url_import"
        dest.mkdir(parents=True, exist_ok=True)
        yml = dest / "skill.yaml"
        yml.write_text(text, encoding="utf-8")
        return await self._install_from_file(str(yml))

    async def _install_dependencies(self, dependencies: list[str]) -> None:
        if not dependencies:
            return
        try:
            await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-m", "pip", "install", *dependencies],
                capture_output=True,
                check=True,
                text=True,
            )
            logger.info("Installed skill dependencies: %s", dependencies)
        except subprocess.CalledProcessError as exc:
            logger.error("pip install failed: %s", exc.stderr)

    async def execute_skill(self, name: str, input_data: dict[str, Any]) -> SkillExecutionResult:
        skill = self.get_skill(name)
        if skill is None:
            return SkillExecutionResult(success=False, output=None, error=f"Skill {name!r} not found")

        # Phase 75 — permission allowlist gate. Runs identically for python
        # and shell execution_types and short-circuits to a structured
        # failure (no module import, no subprocess) when sandbox-mode is on
        # and the skill requested permissions outside the allowlist.
        deny_reason = assert_permissions_allowed(skill)
        if deny_reason:
            return SkillExecutionResult(success=False, output=None, error=deny_reason)

        start = time.perf_counter()

        try:
            if skill.execution_type == "python":
                result = await execute_python_skill(skill, input_data)
            elif skill.execution_type == "shell":
                result = await execute_shell_skill(skill, input_data)
            else:
                return SkillExecutionResult(
                    success=False,
                    output=None,
                    error=f"Unknown execution type: {skill.execution_type}",
                )
            result.duration_ms = (time.perf_counter() - start) * 1000
            return result
        except Exception as exc:  # noqa: BLE001
            return SkillExecutionResult(
                success=False,
                output=None,
                error=str(exc),
                duration_ms=(time.perf_counter() - start) * 1000,
            )


_registry = PluginSkillRegistry()


def get_plugin_skill_registry() -> PluginSkillRegistry:
    return _registry


def default_plugin_skills_dir() -> Path:
    raw = (get_settings().nexa_plugin_skills_root or "").strip()
    if raw:
        return Path(raw)
    return REPO_ROOT / "data" / "nexa_plugin_skills"


__all__ = ["PluginSkillRegistry", "default_plugin_skills_dir", "get_plugin_skill_registry"]
