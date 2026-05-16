# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path

from app.deploy_context.context_validation import workspace_confidence


def test_workspace_confidence_high_signals(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    (root / "package.json").write_text("{}", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".vercel").mkdir()
    (root / ".vercel" / "project.json").write_text("{}", encoding="utf-8")
    (root / "vercel.json").write_text("{}", encoding="utf-8")
    out = workspace_confidence(root)
    assert out["workspace_confidence"] == "high"
    assert "package.json" in out["signals"]
