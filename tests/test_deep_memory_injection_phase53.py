"""Phase 53 — memory context shape and intent classifier wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.intent_classifier import VALID_INTENTS
from app.services.memory.context_injection import build_memory_context_for_turn
from app.services.skills.manifest_registry import SkillPackageRegistry


def test_valid_intents_includes_analysis() -> None:
    assert "analysis" in VALID_INTENTS


def test_build_memory_includes_tags_and_purpose() -> None:
    ctx = build_memory_context_for_turn("u1", "EKS mongo OIDC issue", purpose="test", max_items=3)
    assert ctx.get("purpose") == "test"
    assert isinstance(ctx.get("tags"), list)


def test_skill_registry_empty_dir(tmp_path: Path) -> None:
    reg = SkillPackageRegistry(base_dir=tmp_path / "empty")
    assert reg.list_skills() == []


def test_skill_registry_loads_manifest(tmp_path: Path) -> None:
    d = tmp_path / "demo_skill"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(
        '{"id":"demo","name":"Demo","description":"x","version":"0.1.0","author":"t","permissions":["repo.read"],"risk_level":"low"}',
        encoding="utf-8",
    )
    reg = SkillPackageRegistry(base_dir=tmp_path)
    skills = reg.list_skills()
    assert len(skills) == 1
    assert skills[0].id == "demo"
    assert "repo.read" in skills[0].permissions
