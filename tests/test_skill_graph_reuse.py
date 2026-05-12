# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace intelligence — skill chain hints."""

from __future__ import annotations

from app.services.workspace_intelligence.skills_graph import find_skill_chain


def test_linkedin_transcript_chain() -> None:
    c = find_skill_chain("Create LinkedIn post from podcast transcript")
    assert c[:2] == ["transcript", "hook_finder"]


def test_newsletter_chain() -> None:
    c = find_skill_chain("Draft our weekly newsletter issue")
    assert "hook_finder" in c
