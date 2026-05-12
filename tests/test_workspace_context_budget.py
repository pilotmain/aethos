# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace intelligence — token budget trimming."""

from __future__ import annotations

from pathlib import Path

from app.services.workspace_intelligence.context_pack import build_pack


def test_build_pack_respects_small_token_budget(tmp_path: Path) -> None:
    root = tmp_path / "bud"
    root.mkdir()
    big = "paragraph\n" * 2000
    (root / "a.md").write_text(big, encoding="utf-8")
    (root / "b.md").write_text(big, encoding="utf-8")

    pack = build_pack(
        root,
        ["a.md", "b.md"],
        max_tokens=80,
        skills=[],
    )
    assert pack.token_estimate <= 85  # rough ceiling
    assert len(pack.summary) < len(big) * 2
