"""Workspace intelligence — safe loader paths."""

from __future__ import annotations

from pathlib import Path

from app.services.workspace_intelligence.loader import (
    iter_workspace_files,
    read_workspace_file,
    resolve_workspace_root,
)


def test_resolve_workspace_root_default_under_repo(tmp_path: Path) -> None:
    expected = tmp_path / "data" / "aethos_workspace"
    expected.mkdir(parents=True)
    root = resolve_workspace_root("", repo_root=tmp_path)
    assert root == expected


def test_read_workspace_file_blocks_traversal(tmp_path: Path) -> None:
    r = tmp_path / "wi_root"
    r.mkdir()
    sub = r / "safe"
    sub.mkdir()
    (sub / "a.md").write_text("ok", encoding="utf-8")
    assert read_workspace_file(r, "safe/a.md") == "ok"
    assert read_workspace_file(r, "../safe/a.md") is None
    assert read_workspace_file(r, "safe/../../etc/passwd") is None


def test_iter_workspace_files_sorted(tmp_path: Path) -> None:
    r = tmp_path / "wi2"
    r.mkdir()
    (r / "z.md").write_text("z", encoding="utf-8")
    (r / "a.md").write_text("a", encoding="utf-8")
    assert iter_workspace_files(r) == ["a.md", "z.md"]
