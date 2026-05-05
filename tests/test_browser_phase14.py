"""Phase 14 — browser NL inference + plugin_skill registration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.host_executor_nl_chain import extract_browser_intent, try_infer_browser_automation_nl
from app.services.skills.builtin_register import register_builtin_plugin_skills
from app.services.skills.loader import load_skill_manifest
from app.services.skills.plugin_registry import PluginSkillRegistry


@pytest.fixture()
def isolated_registry() -> PluginSkillRegistry:
    reg = object.__new__(PluginSkillRegistry)
    reg._skills = {}
    return reg


def test_extract_navigate_https() -> None:
    pl = extract_browser_intent("please go to https://example.com/path")
    assert pl is not None
    assert pl["skill_name"] == "browser_navigate"
    assert pl["input"]["url"].startswith("https://")


def test_extract_navigate_bare_host() -> None:
    pl = extract_browser_intent("go to example.com")
    assert pl is not None
    assert pl["input"]["url"].startswith("https://example.com")


def test_try_infer_navigate_and_screenshot_chain() -> None:
    class _S:
        nexa_host_executor_enabled = True
        nexa_browser_enabled = True
        nexa_browser_automation_enabled = False

    with patch("app.services.host_executor_nl_chain.get_settings", return_value=_S()):
        pl = try_infer_browser_automation_nl("go to https://example.com and take a screenshot")
    assert pl is not None
    assert pl.get("host_action") == "chain"
    acts = pl.get("actions") or []
    assert len(acts) == 2
    assert acts[0].get("skill_name") == "browser_navigate"
    assert acts[1].get("skill_name") == "browser_screenshot"


def test_builtin_browser_manifests_resolve(isolated_registry: PluginSkillRegistry) -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "services" / "skills" / "builtin_plugins"
    yml = root / "browser_navigate" / "skill.yaml"
    skill = load_skill_manifest(yml)
    isolated_registry.register(skill)
    assert isolated_registry.get_skill("browser_navigate") is not None


def test_register_builtin_skills_idempotent_no_crash() -> None:
    register_builtin_plugin_skills()
