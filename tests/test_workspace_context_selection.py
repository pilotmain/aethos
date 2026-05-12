# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace intelligence — heuristic file selection."""

from __future__ import annotations

from pathlib import Path

from app.services.workspace_intelligence.selector import select_workspace_context


def test_linkedin_query_prioritizes_voice_and_templates(tmp_path: Path) -> None:
    root = tmp_path / "sel"
    root.mkdir()
    (root / "business").mkdir(parents=True)
    (root / "outputs" / "templates").mkdir(parents=True)
    (root / "business" / "voice-profile.md").write_text("# voice\nlinkedin tone\n", encoding="utf-8")
    (root / "outputs" / "templates" / "linkedin-post.md").write_text("# tpl\n", encoding="utf-8")
    (root / "personality.md").write_text("# p\n", encoding="utf-8")

    ordered, skills = select_workspace_context(
        root,
        "Write a LinkedIn post from this podcast transcript about kubernetes",
    )
    assert "outputs/templates/linkedin-post.md" in ordered
    assert "business/voice-profile.md" in ordered
    assert "transcript" in skills or "hook_finder" in skills


def test_project_slug_boosts_project_file(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "projects").mkdir()
    (root / "projects" / "foo.md").write_text("# Foo stack\n", encoding="utf-8")
    (root / "personality.md").write_text("# p\n", encoding="utf-8")

    ordered, _ = select_workspace_context(root, "generic chat", project_slug="foo")
    assert "projects/foo.md" in ordered[:4]
