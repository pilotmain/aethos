"""Sandbox Development read/show/write fast path (no LLM)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.gateway.context import GatewayContext
from app.services.gateway.sandbox_nl import try_sandbox_development_file_fastpath


def _settings(enabled: bool = True) -> MagicMock:
    return MagicMock(
        nexa_sandbox_execution_enabled=enabled,
        nexa_auto_approve_owner=True,
        nexa_sandbox_execution_max_file_bytes=1_048_576,
    )


def test_sandbox_dev_read_show_in_todo_project(tmp_path: Path) -> None:
    proj = tmp_path / "my-todo-demo"
    proj.mkdir()
    (proj / "index.html").write_text("<html></html>", encoding="utf-8")
    (proj / "app.js").write_text("console.log(1);", encoding="utf-8")
    (proj / "styles.css").write_text("body { color: red; }\n", encoding="utf-8")

    gctx = GatewayContext(user_id="tg_owner")
    with (
        patch(
            "app.services.gateway.sandbox_nl._workspace_root_for_sandbox",
            return_value=str(tmp_path),
        ),
        patch(
            "app.services.gateway.sandbox_nl.is_privileged_owner_for_web_mutations",
            return_value=True,
        ),
        patch("app.services.gateway.sandbox_nl.get_settings", return_value=_settings()),
    ):
        out = try_sandbox_development_file_fastpath(
            gctx,
            "Development show styles.css",
            MagicMock(),
        )
    assert out is not None
    assert out.get("intent") == "sandbox_dev_read"
    assert "color: red" in (out.get("text") or "")


def test_sandbox_dev_read_disabled_returns_none(tmp_path: Path) -> None:
    gctx = GatewayContext(user_id="tg_owner")
    with (
        patch(
            "app.services.gateway.sandbox_nl._workspace_root_for_sandbox",
            return_value=str(tmp_path),
        ),
        patch(
            "app.services.gateway.sandbox_nl.is_privileged_owner_for_web_mutations",
            return_value=True,
        ),
        patch("app.services.gateway.sandbox_nl.get_settings", return_value=_settings(enabled=False)),
    ):
        assert (
            try_sandbox_development_file_fastpath(
                gctx,
                "Development read foo.txt",
                MagicMock(),
            )
            is None
        )


def test_sandbox_dev_write_creates_file(tmp_path: Path) -> None:
    gctx = GatewayContext(user_id="tg_owner")
    with (
        patch(
            "app.services.gateway.sandbox_nl._workspace_root_for_sandbox",
            return_value=str(tmp_path),
        ),
        patch(
            "app.services.gateway.sandbox_nl.is_privileged_owner_for_web_mutations",
            return_value=True,
        ),
        patch("app.services.gateway.sandbox_nl.get_settings", return_value=_settings()),
    ):
        out = try_sandbox_development_file_fastpath(
            gctx,
            'Dev write sub/hello.txt with Hello World',
            MagicMock(),
        )
    assert out is not None
    assert out.get("intent") == "sandbox_dev_write"
    p = tmp_path / "sub" / "hello.txt"
    assert p.read_text(encoding="utf-8") == "Hello World"
