# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Pluggable skill CLI helpers (Phase 6) — used by ``python -m aethos_cli``."""

from __future__ import annotations

import asyncio
import sys


def cmd_skills_list() -> int:
    from app.services.skills.plugin_registry import get_plugin_skill_registry

    reg = get_plugin_skill_registry()
    skills = reg.list_skills()
    if not skills:
        print("(no plugin skills registered)")
        return 0
    for s in skills:
        print(f"  {s.name} — {s.description} (v{s.version})")
    return 0


def cmd_skills_install(name: str, source: str) -> int:
    from app.services.skills.plugin_registry import get_plugin_skill_registry

    reg = get_plugin_skill_registry()
    skill = asyncio.run(reg.install_skill(name, source))
    if skill:
        print(f"Installed plugin skill: {skill.name} v{skill.version}")
        return 0
    print(f"Install failed or deferred: {name!r} source={source!r}", file=sys.stderr)
    return 1


def cmd_skills_remove(name: str) -> int:
    _ = name
    print("remove: not implemented (Phase 6.2)", file=sys.stderr)
    return 2


__all__ = ["cmd_skills_install", "cmd_skills_list", "cmd_skills_remove"]
