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


def test_rejects_traversal_and_unknown() -> None:
    assert infer_host_executor_action("read ../../etc/passwd") is None
    assert infer_host_executor_action("deploy to production") is None
    assert infer_host_executor_action("") is None
