"""Workspace path resolution for QA scans."""

from __future__ import annotations

from pathlib import Path

from app.services.workspace_resolver import extract_path_hint_from_message, resolve_workspace_path


def test_resolve_explicit_existing_tmp(tmp_path: Path) -> None:
    p = tmp_path / "proj"
    p.mkdir()
    got = resolve_workspace_path(str(p), db=None, owner_user_id=None)
    assert got == p.resolve()


def test_extract_path_from_message(tmp_path: Path) -> None:
    p = tmp_path / "repo"
    p.mkdir()
    msg = f"Review vulnerabilities in {p}"
    assert extract_path_hint_from_message(msg) == str(p.resolve())
