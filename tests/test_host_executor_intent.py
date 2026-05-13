# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""infer_host_executor_action maps safe short phrases only."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.services.host_executor_intent import (
    infer_host_executor_action,
    parse_development_task_intent,
    parse_start_app_intent,
)


def test_parse_start_app_intent() -> None:
    assert parse_start_app_intent("start the todo app") == {
        "intent": "start_app",
        "kind": "todo",
        "slug": None,
        "raw_text": "start the todo app",
    }
    assert parse_start_app_intent("Run my react app")["kind"] == "react"
    assert parse_start_app_intent("launch the app")["kind"] == "recent"
    assert parse_start_app_intent("start the demo-widget app") == {
        "intent": "start_app",
        "kind": "named",
        "slug": "demo-widget",
        "raw_text": "start the demo-widget app",
    }
    assert parse_start_app_intent("start the") is None


def test_parse_development_task_intent() -> None:
    p = parse_development_task_intent("Development add a delete button")
    assert p and p["intent"] == "development_task" and "delete" in p["task"]
    assert parse_development_task_intent("dev fix the API timeout")["task"].startswith("fix")
    assert parse_development_task_intent("deploy to vercel") is None


def test_git_status_variants() -> None:
    for s in ("git status", "check git status", "please check git status", "show git status"):
        out = infer_host_executor_action(s)
        assert out == {"host_action": "git_status"}


def test_vercel_projects_list_phrase() -> None:
    assert infer_host_executor_action("list my vercel projects") == {
        "host_action": "vercel_projects_list",
    }
    assert infer_host_executor_action("vercel projects list")["host_action"] == "vercel_projects_list"


def test_git_push_phrase() -> None:
    assert infer_host_executor_action("git push") == {"host_action": "git_push"}
    assert infer_host_executor_action("please git push")["host_action"] == "git_push"


def test_run_tests_pytest() -> None:
    assert infer_host_executor_action("run tests") == {
        "host_action": "run_command",
        "run_name": "pytest",
    }
    assert infer_host_executor_action("run pytest")["host_action"] == "run_command"


def test_read_file(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# hi", encoding="utf-8")
    (tmp_path / "src" / "app").mkdir(parents=True)
    (tmp_path / "src" / "app" / "main.py").write_text("x = 1", encoding="utf-8")

    class S:
        host_executor_work_root = str(tmp_path.resolve())

    with patch("app.services.host_executor_intent.get_settings", return_value=S()):
        assert infer_host_executor_action("read file README.md") == {
            "host_action": "file_read",
            "relative_path": "README.md",
        }
    with patch("app.services.host_executor_intent.get_settings", return_value=S()):
        assert infer_host_executor_action("show src/app/main.py")["host_action"] == "file_read"


def test_write_file_requires_body() -> None:
    assert infer_host_executor_action("write notes.txt with hello") == {
        "host_action": "file_write",
        "relative_path": "notes.txt",
        "content": "hello",
    }


def test_create_file_with_content_in_absolute_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "aethos_workspace"

    class S:
        host_executor_work_root = str(tmp_path.resolve())

    with patch("app.services.host_executor_intent.get_settings", return_value=S()):
        assert infer_host_executor_action(
            f"Create a file called test.txt with content 'Hello AethOS' in {workspace}"
        ) == {
            "host_action": "file_write",
            "relative_path": "aethos_workspace/test.txt",
            "content": "Hello AethOS",
        }


def test_write_quoted_content_to_absolute_file(tmp_path: Path) -> None:
    target = tmp_path / "aethos_workspace" / "simple_test.txt"

    class S:
        host_executor_work_root = str(tmp_path.resolve())

    with patch("app.services.host_executor_intent.get_settings", return_value=S()):
        assert infer_host_executor_action(f"Write 'test content' to {target}") == {
            "host_action": "file_write",
            "relative_path": "aethos_workspace/simple_test.txt",
            "content": "test content",
        }


def test_infer_run_mkdir_command(tmp_path: Path) -> None:
    class S:
        host_executor_work_root = str(tmp_path.resolve())

    with patch("app.services.host_executor_intent.get_settings", return_value=S()):
        out = infer_host_executor_action("run mkdir -p scratch_dir")
    assert out == {
        "host_action": "run_command",
        "command": "mkdir -p scratch_dir",
        "command_type": "run_command",
    }


def test_infer_npm_install_in_dir_optional(tmp_path: Path) -> None:
    class S:
        host_executor_work_root = str(tmp_path.resolve())

    pkg = tmp_path / "my-pkg"
    pkg.mkdir(parents=True, exist_ok=True)

    with patch("app.services.host_executor_intent.get_settings", return_value=S()):
        out = infer_host_executor_action(f"npm install in {pkg}")
    assert out and out.get("host_action") == "run_command"
    assert "npm install" in (out.get("command") or "")


def test_browser_host_commands_infer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_HOST_EXECUTOR_ENABLED", "1")
    monkeypatch.setenv("NEXA_BROWSER_ENABLED", "true")
    monkeypatch.setenv("HOST_EXECUTOR_WORK_ROOT", str(tmp_path.resolve()))
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert infer_host_executor_action("open https://example.com/path") == {
            "host_action": "browser_open",
            "url": "https://example.com/path",
        }
        assert infer_host_executor_action("navigate to https://ex.org") == {
            "host_action": "browser_open",
            "url": "https://ex.org",
        }
        assert infer_host_executor_action("click #submit") == {
            "host_action": "browser_click",
            "selector": "#submit",
        }
        assert infer_host_executor_action("type hello into #q") == {
            "host_action": "browser_fill",
            "selector": "#q",
            "text": "hello",
        }
        assert infer_host_executor_action("screenshot") == {"host_action": "browser_screenshot"}
        assert infer_host_executor_action("screenshot page1") == {
            "host_action": "browser_screenshot",
            "name": "page1",
        }
    finally:
        monkeypatch.delenv("NEXA_HOST_EXECUTOR_ENABLED", raising=False)
        monkeypatch.delenv("NEXA_BROWSER_ENABLED", raising=False)
        monkeypatch.delenv("HOST_EXECUTOR_WORK_ROOT", raising=False)
        get_settings.cache_clear()


def test_browser_host_commands_disabled_without_host_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEXA_HOST_EXECUTOR_ENABLED", "0")
    monkeypatch.setenv("NEXA_BROWSER_ENABLED", "true")
    monkeypatch.setenv("HOST_EXECUTOR_WORK_ROOT", str(tmp_path.resolve()))
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert infer_host_executor_action("open https://example.com") is None
    finally:
        monkeypatch.delenv("NEXA_HOST_EXECUTOR_ENABLED", raising=False)
        monkeypatch.delenv("NEXA_BROWSER_ENABLED", raising=False)
        monkeypatch.delenv("HOST_EXECUTOR_WORK_ROOT", raising=False)
        get_settings.cache_clear()
