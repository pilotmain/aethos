# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 47C — validate_commit and repo sanity helpers."""

from __future__ import annotations

import subprocess

from app.core.config import get_settings
from app.services.dev_runtime.git_tools import repo_sanity_check, rollback_last_commit, validate_commit


def test_repo_sanity_passes_on_fresh_git_repo(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    get_settings.cache_clear()
    try:
        repo = tmp_path / "san"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@test.local"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
        (repo / "a.txt").write_text("x", encoding="utf-8")
        subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
        out = repo_sanity_check(repo)
        assert out.get("ok") is True
    finally:
        monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
        get_settings.cache_clear()


def test_validate_commit_runs_after_commit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    get_settings.cache_clear()
    try:
        repo = tmp_path / "vc"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@test.local"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
        (repo / "README.md").write_text("# x\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "c"], cwd=repo, check=True, capture_output=True)
        tdir = repo / "tests"
        tdir.mkdir()
        (tdir / "test_dummy_phase47.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        vc = validate_commit(repo)
        assert "tests" in vc
        assert vc.get("head")
    finally:
        monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
        get_settings.cache_clear()


def test_rollback_last_commit_respects_gate(tmp_path) -> None:
    rb = rollback_last_commit(tmp_path, allow_commit=False)
    assert rb.get("ok") is False
