"""Phase 25 — diff summary for agent context."""

from __future__ import annotations

import subprocess

from app.services.dev_runtime.git_tools import get_diff_summary


def test_get_diff_summary_counts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    from app.core.config import get_settings

    get_settings.cache_clear()
    repo = tmp_path / "gd"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "a.txt").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "a.txt").write_text("hello world", encoding="utf-8")
    s = get_diff_summary(repo)
    assert s.get("has_uncommitted") is True
    assert (s.get("diff_chars") or 0) > 0
    monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
    get_settings.cache_clear()
