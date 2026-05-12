"""Sandbox allowlist and executor (workspace-scoped)."""

from __future__ import annotations

from pathlib import Path

from app.services.sandbox.action_allowlist import is_action_allowed, validate_plan_actions
from app.services.sandbox.plan_executor import SandboxExecutor


def test_is_action_allowed_rejects_rm() -> None:
    ws = Path("/tmp/ws").resolve()
    ok, msg = is_action_allowed(
        "run_command",
        {"command": "rm -rf x", "cwd": "."},
        workspace_root=ws,
        max_file_bytes=1000,
    )
    assert ok is False
    assert "Blocked" in msg or "not in" in msg


def test_is_action_allowed_accepts_npm_install(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    sub = root / "app"
    sub.mkdir()
    ok, msg = is_action_allowed(
        "run_command",
        {"command": "npm install", "cwd": "app"},
        workspace_root=root.resolve(),
        max_file_bytes=1000,
    )
    assert ok is True, msg


def test_executor_write_and_rollback(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    f = root / "a.txt"
    f.write_text("old", encoding="utf-8")
    plan = {
        "explanation": "test",
        "actions": [
            {"type": "write_file", "params": {"path": "a.txt", "content": "new"}},
            {"type": "run_command", "params": {"command": "false", "cwd": "."}},
        ],
    }
    ex = SandboxExecutor(root, max_file_bytes=10_000, command_timeout_seconds=5)
    out = ex.execute_plan(plan, user_id="u1")
    assert out["success"] is False
    assert f.read_text(encoding="utf-8") == "old"


def test_executor_read_file_resolves_todo_subfolder(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    proj = root / "my-todo-demo"
    proj.mkdir()
    (proj / "index.html").write_text("<html/>", encoding="utf-8")
    (proj / "app.js").write_text("// app", encoding="utf-8")
    (proj / "styles.css").write_text("body { color: red; }", encoding="utf-8")

    plan = {
        "explanation": "read css",
        "actions": [{"type": "read_file", "params": {"path": "styles.css"}}],
    }
    ex = SandboxExecutor(root, max_file_bytes=10_000, command_timeout_seconds=5)
    out = ex.execute_plan(plan, user_id="u1")
    assert out["success"] is True, out
    previews = [r.get("preview", "") for r in out["results"] if r.get("action") == "read_file"]
    assert previews and "color: red" in previews[0]
    assert any("my-todo-demo" in str(r.get("path", "")) for r in out["results"])
