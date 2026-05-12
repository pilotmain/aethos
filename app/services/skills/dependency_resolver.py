# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 75 — cross-skill dependency resolver.

The existing :class:`~app.services.skills.installer.SkillInstaller` only
processes ``manifest.dependencies`` (pip packages). Phase 75 introduces a
**separate** ``skill_dependencies`` channel on both
:class:`~app.services.skills.loader.SkillManifest` and
:class:`~app.services.skills.clawhub_models.ClawHubSkillInfo`. This module
walks that graph BEFORE the host skill is registered, installing missing
ClawHub skills first.

Design notes (safe-adapt v1):

* **Pre-install resolution.** The resolver runs against the *remote* metadata
  (``ClawHubClient.get_skill_info``) so we can plan the full graph without
  touching disk. The host skill itself is installed by the caller (the
  existing :func:`SkillInstaller.install`) only if planning succeeds.
* **Cycle detection.** A simple DFS visit-set prevents infinite loops.
  Cycles raise :class:`SkillDependencyError("cycle")` and abort the whole
  install — partial progress is preserved (already-installed children stay
  installed; the failing host is never registered).
* **Missing dependency.** If any node returns ``None`` from the registry
  (404 / network failure / unknown name) the resolver raises
  :class:`SkillDependencyError("missing:<name>")` — the caller should map
  this to a 502 / 404 surface.
* **Already installed.** Skills already present in ``installed.yaml`` are
  short-circuited; we don't re-install or re-check their version (the
  separate :mod:`update_checker` handles freshness).
* **No pip dep handling.** Pip packages stay on the
  ``SkillInstaller._install_dependencies`` path via ``ensure_dependencies``;
  this module is strictly cross-skill.

This file is import-light: it does NOT take a hard dependency on
``SkillInstaller`` at import time (avoids circular import with the installer
which itself imports ``ClawHubClient``); the installer is resolved lazily.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.services.skills.clawhub_client import ClawHubClient
from app.services.skills.clawhub_models import ClawHubSkillInfo

if TYPE_CHECKING:  # pragma: no cover
    from app.services.skills.installer import SkillInstaller

logger = logging.getLogger(__name__)


class SkillDependencyError(RuntimeError):
    """Structured error from the resolver. ``code`` matches the upstream contract."""

    def __init__(self, code: str, *, name: str | None = None) -> None:
        self.code = code
        self.name = name
        super().__init__(code if name is None else f"{code}:{name}")


@dataclass
class DependencyPlanNode:
    """One step in the install plan."""

    name: str
    version: str
    publisher: str
    skill_dependencies: list[str] = field(default_factory=list)
    already_installed: bool = False


@dataclass
class DependencyPlan:
    """Fully resolved dependency plan, in install order (leaves first)."""

    nodes: list[DependencyPlanNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[dict[str, str | bool | list[str]]]]:
        return {
            "plan": [
                {
                    "name": n.name,
                    "version": n.version,
                    "publisher": n.publisher,
                    "skill_dependencies": list(n.skill_dependencies),
                    "already_installed": n.already_installed,
                }
                for n in self.nodes
            ]
        }


class SkillDependencyResolver:
    """Walk the cross-skill dependency graph and produce an install plan.

    The resolver is intentionally tiny — no concurrency, no batching. The
    typical install graph is 0-3 nodes deep; serialised resolution keeps
    failure mapping simple ("first failure wins") and avoids juggling
    partial state in the installer.
    """

    def __init__(
        self,
        *,
        client: ClawHubClient | None = None,
        installer: "SkillInstaller | None" = None,
        max_depth: int = 10,
    ) -> None:
        self.client = client or ClawHubClient()
        self._installer = installer  # lazy-resolved if None
        self.max_depth = max_depth

    # ---------------------------------------------------------------- planning

    async def plan(self, head_info: ClawHubSkillInfo) -> DependencyPlan:
        """Return the leaves-first install plan for ``head_info``.

        The head itself is included as the *last* node so callers can iterate
        the plan top-to-bottom and install in order.
        """
        plan: DependencyPlan = DependencyPlan()
        installed_names = {s.name for s in self._get_installer().list_installed()}
        await self._visit(
            info=head_info,
            plan=plan,
            visiting=set(),
            installed_names=installed_names,
            depth=0,
        )
        return plan

    async def _visit(
        self,
        *,
        info: ClawHubSkillInfo,
        plan: DependencyPlan,
        visiting: set[str],
        installed_names: set[str],
        depth: int,
    ) -> None:
        nm = info.name.strip()
        if depth > self.max_depth:
            raise SkillDependencyError("max_depth_exceeded", name=nm)
        if nm in visiting:
            raise SkillDependencyError("cycle", name=nm)
        if any(node.name == nm for node in plan.nodes):
            return  # already planned via another branch; idempotent
        visiting.add(nm)
        try:
            for dep_name in info.skill_dependencies:
                dep_clean = (dep_name or "").strip()
                if not dep_clean:
                    continue
                if dep_clean in installed_names:
                    plan.nodes.append(
                        DependencyPlanNode(
                            name=dep_clean,
                            version="",
                            publisher="",
                            skill_dependencies=[],
                            already_installed=True,
                        )
                    )
                    continue
                child_info = await self.client.get_skill_info(dep_clean)
                if child_info is None:
                    raise SkillDependencyError("missing", name=dep_clean)
                await self._visit(
                    info=child_info,
                    plan=plan,
                    visiting=visiting,
                    installed_names=installed_names,
                    depth=depth + 1,
                )
            plan.nodes.append(
                DependencyPlanNode(
                    name=nm,
                    version=info.version,
                    publisher=info.publisher,
                    skill_dependencies=list(info.skill_dependencies),
                    already_installed=nm in installed_names,
                )
            )
        finally:
            visiting.discard(nm)

    # ----------------------------------------------------------- execute plan

    async def install_dependencies(
        self, head_info: ClawHubSkillInfo
    ) -> tuple[DependencyPlan, list[str]]:
        """Walk the plan and install every cross-skill dependency.

        The head itself is **NOT** installed here — only its dependencies.
        Returns the resolved plan plus the list of names actually installed
        (in order). On failure raises :class:`SkillDependencyError` with a
        ``code`` matching the deepest failure ("missing", "install_failed",
        "cycle", "max_depth_exceeded").

        Already-installed nodes and the head node are skipped silently.
        """
        plan = await self.plan(head_info)
        newly_installed: list[str] = []
        installer = self._get_installer()
        for node in plan.nodes:
            if node.name == head_info.name:
                continue
            if node.already_installed:
                continue
            ok, msg, _ = await installer.install(
                node.name, node.version or "latest", force=False
            )
            if not ok:
                logger.warning(
                    "dependency install failed name=%s err=%s", node.name, msg
                )
                raise SkillDependencyError(f"install_failed:{msg}", name=node.name)
            newly_installed.append(node.name)
        return plan, newly_installed

    # --------------------------------------------------------------- helpers

    def _get_installer(self) -> "SkillInstaller":
        if self._installer is None:
            from app.services.skills.installer import SkillInstaller

            self._installer = SkillInstaller()
        return self._installer


__all__ = [
    "DependencyPlan",
    "DependencyPlanNode",
    "SkillDependencyError",
    "SkillDependencyResolver",
]
