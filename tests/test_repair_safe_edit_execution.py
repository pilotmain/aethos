# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path

from app.providers.repair.repair_safe_edits import apply_safe_edit, is_protected_relative_path


def test_protected_env_path() -> None:
    assert is_protected_relative_path(".env")
    assert is_protected_relative_path("node_modules/foo")


def test_safe_edit_replace(tmp_path: Path) -> None:
    repo = tmp_path / "app"
    repo.mkdir()
    target = repo / "readme.txt"
    target.write_text("old", encoding="utf-8")
    row = apply_safe_edit(repo, {"path": "readme.txt", "operation": "replace", "content": "new"})
    assert row["ok"] is True
    assert target.read_text(encoding="utf-8") == "new"
