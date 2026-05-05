"""Phase 6 pluggable skill registry."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.services.skills.plugin_registry import PluginSkillRegistry, get_plugin_skill_registry


@pytest.fixture()
def isolated_registry() -> PluginSkillRegistry:
    """Fresh registry instance (bypass singleton for isolation)."""
    reg = object.__new__(PluginSkillRegistry)
    reg._skills = {}
    return reg


def test_load_and_execute_echo_skill(isolated_registry: PluginSkillRegistry, tmp_path: Path) -> None:
    skill_dir = tmp_path / "echo-skill"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text(
        """
name: echo-skill
version: 0.0.1
description: Echo input
author: test
tags: [test]
input_schema: {}
output_schema: {}
execution:
  type: python
  entry: handler.py
  handler: run
dependencies: []
permissions: []
""".strip(),
        encoding="utf-8",
    )
    (skill_dir / "handler.py").write_text(
        'def run(msg: str = ""):\n    return {"echo": msg}\n',
        encoding="utf-8",
    )

    skill = asyncio.run(isolated_registry.install_skill("echo-skill", f"file://{skill_dir/'skill.yaml'}"))
    assert skill is not None
    assert skill.name == "echo-skill"

    result = asyncio.run(isolated_registry.execute_skill("echo-skill", {"msg": "hi"}))
    assert result.success
    assert result.output == {"echo": "hi"}


def test_get_plugin_skill_registry_singleton() -> None:
    a = get_plugin_skill_registry()
    b = get_plugin_skill_registry()
    assert a is b
