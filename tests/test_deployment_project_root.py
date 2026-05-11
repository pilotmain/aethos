"""Tests for deployment project-root resolution."""

from __future__ import annotations

from pathlib import Path

from app.services.deployment.project_layout import find_project_root


def test_find_project_root_prefers_nested_package_json(tmp_path: Path) -> None:
    nested = tmp_path / "myapp"
    nested.mkdir()
    (nested / "package.json").write_text("{}")

    assert find_project_root(tmp_path) == nested.resolve()


def test_find_project_root_stays_when_multiple_nested_markers(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "package.json").write_text("{}")
    (b / "package.json").write_text("{}")

    assert find_project_root(tmp_path) == tmp_path.resolve()


def test_find_project_root_direct_marker(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")

    assert find_project_root(tmp_path) == tmp_path.resolve()
