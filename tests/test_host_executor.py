# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Controlled host executor: allowlists, paths, timeouts (no unrestricted shell)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services import host_executor


class _Settings:
    nexa_host_executor_enabled = True
    host_executor_work_root = ""
    host_executor_timeout_seconds = 120
    host_executor_max_file_bytes = 262_144
    nexa_browser_enabled = True

    def __init__(self, root: Path) -> None:
        self.host_executor_work_root = str(root)


def test_execute_disabled_raises() -> None:
    class _Off:
        nexa_host_executor_enabled = False

    with patch.object(host_executor, "get_settings", return_value=_Off()):
        with pytest.raises(ValueError, match="disabled"):
            host_executor.execute_payload({"host_action": "git_status"})


def test_unknown_run_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        with pytest.raises(ValueError, match="unknown or disallowed run_name"):
            host_executor.execute_payload({"host_action": "run_command", "run_name": "rm_rf"})


def test_path_traversal_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "safe.txt").write_text("ok", encoding="utf-8")
    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        with pytest.raises(ValueError, match=r"\.\.|escape"):
            host_executor.execute_payload(
                {"host_action": "file_read", "relative_path": "../outside"}
            )


def test_git_status_runs_in_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env={**dict(__import__("os").environ), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )

    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        out = host_executor.execute_payload({"host_action": "git_status"})
        assert "README" in out or "##" in out or "main" in out.lower() or "master" in out.lower()


def test_pytest_allowlist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        out = host_executor.execute_payload({"host_action": "run_command", "run_name": "pytest"})
        assert "no tests collected" in out.lower() or "exit" in out.lower() or out.strip() != ""


def test_vercel_projects_list_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):

        def fake_run(
            argv: list[str], *, cwd: object, timeout: int
        ) -> tuple[int, str, str]:
            assert argv[:3] == ["vercel", "projects", "list"]
            return 0, "  my-proj  ", ""

        with patch.object(host_executor, "_run_argv", side_effect=fake_run):
            out = host_executor.execute_payload({"host_action": "vercel_projects_list"})
            assert "my-proj" in out


def test_vercel_remove_argv_requires_confirm() -> None:
    assert host_executor.argv_for_vercel_remove(
        {"vercel_project_name": "foo-bar", "vercel_yes": True}
    ) == ["vercel", "remove", "foo-bar", "--yes"]
    with pytest.raises(ValueError, match="vercel_yes"):
        host_executor.argv_for_vercel_remove({"vercel_project_name": "foo-bar"})
    with pytest.raises(ValueError, match="slug"):
        host_executor.argv_for_vercel_remove(
            {"vercel_project_name": "../evil", "vercel_yes": True}
        )


def test_git_push_argv_and_validation() -> None:
    assert host_executor.argv_for_git_push({}) == ["git", "push"]
    assert host_executor.argv_for_git_push({"push_remote": "origin"}) == [
        "git",
        "push",
        "origin",
    ]
    assert host_executor.argv_for_git_push(
        {"push_remote": "origin", "push_ref": "main"}
    ) == ["git", "push", "origin", "main"]
    with pytest.raises(ValueError, match="push_ref requires"):
        host_executor.argv_for_git_push({"push_ref": "main"})
    with pytest.raises(ValueError, match="push_remote"):
        host_executor.argv_for_git_push({"push_remote": "bad;rm"})


def test_git_push_fails_without_remote_in_bare_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """git push with no upstream produces non-zero exit; surface stderr."""
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env={
            **dict(__import__("os").environ),
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t",
        },
    )
    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        out = host_executor.execute_payload({"host_action": "git_push"})
        assert "git push failed" in out.lower() or "exit" in out.lower()


def test_timeout_returns_nonzero_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    def boom(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd=["x"], timeout=1)

    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        with patch.object(host_executor.subprocess, "run", side_effect=boom):
            code, _o, err = host_executor._run_argv(["git", "status"], cwd=tmp_path, timeout=1)
            assert code == -1
            assert "timeout" in err.lower()


def test_host_executor_job_dispatches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env={**dict(__import__("os").environ), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )

    job = MagicMock()
    job.payload_json = {"host_action": "git_status"}
    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        text = host_executor.execute_host_executor_job(job)
        assert isinstance(text, str) and len(text) > 0


def test_proposed_risk_level() -> None:
    assert host_executor.proposed_risk_level({"host_action": "git_commit"}) == "high"
    assert host_executor.proposed_risk_level({"host_action": "git_push"}) == "high"
    assert host_executor.proposed_risk_level({"host_action": "vercel_remove"}) == "high"
    assert host_executor.proposed_risk_level({"host_action": "vercel_projects_list"}) == "normal"
    assert host_executor.proposed_risk_level({"host_action": "file_write"}) == "high"
    assert host_executor.proposed_risk_level({"host_action": "git_status"}) == "low"
    assert host_executor.proposed_risk_level({"host_action": "read_multiple_files"}) == "normal"


def test_read_multiple_files_text_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.txt").write_text("hello world", encoding="utf-8")
    (docs / "skip.bin").write_bytes(b"\x00\x01\x02\xff")
    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        out = host_executor.execute_payload(
            {
                "host_action": "read_multiple_files",
                "relative_path": "docs",
                "extensions": [".txt"],
            }
        )
    assert "a.txt" in out
    assert "hello world" in out
    assert "skip.bin" not in out


def test_read_multiple_files_respects_max_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    for i in range(25):
        (tmp_path / f"f{i}.txt").write_text("x", encoding="utf-8")

    class _Lim(_Settings):
        host_executor_read_multiple_max_files = 3

    with patch.object(host_executor, "get_settings", return_value=_Lim(tmp_path)):
        out = host_executor.execute_payload(
            {
                "host_action": "read_multiple_files",
                "relative_path": ".",
                "glob": "*.txt",
            }
        )
    assert out.count("=== FILE:") <= 3


def test_read_multiple_files_nexa_permission_abs_targets_outside_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Approved-folder reads use ``nexa_permission_abs_targets[0]`` as directory base."""
    monkeypatch.chdir(tmp_path)
    outer = tmp_path.parent / "nexa_rm_abs_outer"
    outer.mkdir(exist_ok=True)
    sub = outer / "nested"
    sub.mkdir()
    (sub / "hello.txt").write_text("outside root text", encoding="utf-8")

    outer_res = str(outer.resolve())
    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        out = host_executor.execute_payload(
            {
                "host_action": "read_multiple_files",
                "relative_path": ".",
                "nexa_permission_abs_targets": [outer_res],
                "base": outer_res,
                "extensions": [".txt"],
            }
        )
    assert "nested/hello.txt" in out
    assert "outside root text" in out


def test_read_multiple_files_abs_targets_mismatching_base_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    outer = tmp_path.parent / "nexa_rm_abs_outer_mismatch"
    outer.mkdir(exist_ok=True)
    other = tmp_path / "other_dir"
    other.mkdir()

    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        with pytest.raises(ValueError, match="must match"):
            host_executor.execute_payload(
                {
                    "host_action": "read_multiple_files",
                    "nexa_permission_abs_targets": [str(outer.resolve())],
                    "base": str(other.resolve()),
                    "relative_path": ".",
                }
            )


def test_read_multiple_files_abs_targets_without_base_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With abs targets, ``base`` must be set and match — no silent inference from abs alone."""
    monkeypatch.chdir(tmp_path)
    outer = tmp_path.parent / "nexa_rm_abs_outer2"
    outer.mkdir(exist_ok=True)

    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        with pytest.raises(ValueError, match="missing base"):
            host_executor.execute_payload(
                {
                    "host_action": "read_multiple_files",
                    "nexa_permission_abs_targets": [str(outer.resolve())],
                    "relative_path": ".",
                    "extensions": [".txt"],
                }
            )


def test_read_multiple_env_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")
    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        with pytest.raises(ValueError, match="blocked"):
            host_executor.execute_payload(
                {
                    "host_action": "read_multiple_files",
                    "relative_paths": [".env"],
                }
            )


def test_find_files_extension_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "b.txt").write_text("y", encoding="utf-8")
    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        out = host_executor.execute_payload(
            {
                "host_action": "find_files",
                "relative_path": ".",
                "glob": "*",
                "extensions": [".py"],
            }
        )
    assert "a.py" in out
    assert "b.txt" not in out


def test_browser_host_action_routes_to_playwright_bridge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with patch.object(host_executor, "get_settings", return_value=_Settings(tmp_path)):
        with patch(
            "app.services.browser_automation.run_browser_host_action_sync",
            return_value="ok: navigated",
        ) as mock_run:
            out = host_executor.execute_payload(
                {"host_action": "browser_open", "url": "https://example.com/foo"}
            )
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0]
    assert call_args[0] == "browser_open"
    assert call_args[1]["url"] == "https://example.com/foo"
    assert "ok: navigated" in out
