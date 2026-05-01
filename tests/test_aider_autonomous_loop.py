"""Unit tests for Aider autonomous loop helpers (no aider binary required)."""
from __future__ import annotations

from types import SimpleNamespace

from unittest.mock import patch

from app.services.aider_autonomous_loop import format_approval_message, run_aider_subprocess


def test_format_approval_message_contains_job_id() -> None:
    job = SimpleNamespace(id=42, title="x")
    t = format_approval_message(job, "hello " * 500)
    assert "42" in t
    tlow = t.lower()
    assert "approve" in tlow
    assert "show diff" in tlow


@patch("app.services.aider_autonomous_loop._run")
def test_run_aider_replaces_task_file_placeholder(mock_run, monkeypatch) -> None:
    monkeypatch.setenv("DEV_AGENT_COMMAND", "echo {task_file} {TASK_FILE}")
    p = __import__("pathlib").Path("/tmp/t.md")
    mock_run.return_value = SimpleNamespace(stdout="ok", stderr="")
    out = run_aider_subprocess(p)
    assert out == "ok"
    pos, kw = mock_run.call_args
    cmd = pos[0] if pos else ""
    assert str(p) in cmd
    assert kw.get("shell") is True
