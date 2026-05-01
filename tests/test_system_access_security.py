"""Phase 39 — system access allowlist + workspace paths."""

from __future__ import annotations

import pytest

from app.services.system_access.files import read_text_file
from app.services.system_access.permissions import assert_workspace_path
from app.services.system_access.shell import run_allowlisted_shell


def test_assert_workspace_path_rejects_escape(tmp_path) -> None:
    root = tmp_path / "w"
    root.mkdir()
    good = root / "a.txt"
    good.write_text("x", encoding="utf-8")
    p = assert_workspace_path(good, roots=[str(root)])
    assert p.name == "a.txt"
    outside = tmp_path / "evil.txt"
    outside.write_text("n", encoding="utf-8")
    with pytest.raises(ValueError):
        assert_workspace_path(outside, roots=[str(root)])


def test_read_text_file_respects_root(tmp_path) -> None:
    root = tmp_path / "w"
    root.mkdir()
    f = root / "f.txt"
    f.write_text("data", encoding="utf-8")
    t = read_text_file(f, roots=[str(root)])
    assert t == "data"


def test_shell_not_allowlisted() -> None:
    out = run_allowlisted_shell(
        ["rm", "-rf", "/"],
        allowlist=frozenset({("git", "status")}),
    )
    assert out.get("ok") is False
    assert out.get("error") == "not_allowlisted"
