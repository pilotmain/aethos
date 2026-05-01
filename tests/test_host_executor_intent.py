"""infer_host_executor_action maps safe short phrases only."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.services.host_executor_intent import infer_host_executor_action


def test_git_status_variants() -> None:
    for s in ("git status", "check git status", "please check git status", "show git status"):
        out = infer_host_executor_action(s)
        assert out == {"host_action": "git_status"}


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


def test_rejects_traversal_and_unknown() -> None:
    assert infer_host_executor_action("read ../../etc/passwd") is None
    assert infer_host_executor_action("deploy to production") is None
    assert infer_host_executor_action("") is None

