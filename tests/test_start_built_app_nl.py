# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Gateway NL: start built workspace apps."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.gateway.context import GatewayContext
from app.services.gateway.start_built_app_nl import try_start_built_app_gateway_turn


def test_start_todo_with_backend_owner(tmp_path: Path) -> None:
    proj = tmp_path / "demo-todo-app"
    proj.mkdir()
    (proj / "index.html").write_text("<html/>", encoding="utf-8")
    back = proj / "backend"
    back.mkdir(parents=True)
    (back / "server.js").write_text("//", encoding="utf-8")

    gctx = GatewayContext(user_id="tg_owner")

    with (
        patch(
            "app.services.gateway.start_built_app_nl._workspace_root_for_nl",
            return_value=str(tmp_path),
        ),
        patch(
            "app.services.gateway.start_built_app_nl.is_privileged_owner_for_web_mutations",
            return_value=True,
        ),
        patch("app.services.gateway.start_built_app_nl.get_settings") as gs,
        patch("app.services.gateway.start_built_app_nl.shutil.which", return_value="/fake/node"),
        patch("app.services.gateway.start_built_app_nl.subprocess.Popen") as popen,
        patch("webbrowser.open") as wb,
    ):
        gs.return_value = MagicMock(nexa_auto_approve_owner=True)
        out = try_start_built_app_gateway_turn(gctx, "start the todo app", MagicMock())
        assert out is not None
        assert out.get("intent") == "start_app_success"
        popen.assert_called_once()
        args, kwargs = popen.call_args
        assert args[0] == ["/fake/node", "server.js"]
        assert kwargs.get("cwd") == str(back)
        wb.assert_called_once()


def test_start_app_non_owner_returns_none(tmp_path: Path) -> None:
    gctx = GatewayContext(user_id="other")
    with (
        patch(
            "app.services.gateway.start_built_app_nl._workspace_root_for_nl",
            return_value=str(tmp_path),
        ),
        patch(
            "app.services.gateway.start_built_app_nl.is_privileged_owner_for_web_mutations",
            return_value=False,
        ),
        patch("app.services.gateway.start_built_app_nl.get_settings") as gs,
    ):
        gs.return_value = MagicMock(nexa_auto_approve_owner=True)
        assert try_start_built_app_gateway_turn(gctx, "start the todo app", MagicMock()) is None
