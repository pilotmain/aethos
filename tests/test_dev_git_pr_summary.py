"""Phase 24 — git PR summary helpers."""

from __future__ import annotations

import uuid

from app.models.dev_runtime import NexaDevWorkspace
from app.services.dev_runtime.git_tools import changed_files, create_commit, prepare_pr_summary
from app.services.dev_runtime.github_pr import create_pull_request


def test_prepare_pr_summary_includes_workspace(db_session, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    from app.core.config import get_settings

    get_settings.cache_clear()
    repo = tmp_path / "git_ws"
    repo.mkdir()
    ws = NexaDevWorkspace(
        id=str(uuid.uuid4()),
        user_id="u1",
        name="w",
        repo_path=str(repo),
        status="ready",
    )
    run_blob = {"goal": "g", "adapter_used": "local_stub"}
    out = prepare_pr_summary(ws, run_blob)
    assert out["workspace_id"] == ws.id
    assert out.get("adapter_used") == "local_stub"


def test_changed_files_empty_git_repo(db_session, tmp_path, monkeypatch) -> None:
    import subprocess

    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    from app.core.config import get_settings

    get_settings.cache_clear()
    repo = tmp_path / "empty_git"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    assert changed_files(repo) == []


def test_create_commit_requires_allow_commit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    from app.core.config import get_settings

    get_settings.cache_clear()
    r = create_commit(tmp_path / "nope", "msg", allow_commit=False)
    assert r.get("ok") is False


def test_github_pr_stub_disabled(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_GITHUB_PR_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    r = create_pull_request(goal="x", run_result={"steps": []}, workspace_id="w1")
    assert r["ok"] is False
    assert "not enabled" in str(r.get("reason", "")).lower()
