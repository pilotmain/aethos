# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lightweight e2e-style checks for provider operations (mocked; no real Vercel)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.core.config import get_settings
from app.providers.actions import vercel_actions
from app.runtime.runtime_state import default_runtime_state, save_runtime_state


def test_e2e_style_redeploy_path_records_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    repo = tmp_path / "app"
    repo.mkdir()
    (repo / "package.json").write_text('{"name":"e2e"}', encoding="utf-8")
    (repo / ".vercel").mkdir()
    (repo / ".vercel" / "project.json").write_text(
        '{"projectId":"pid","orgId":"oid","projectName":"e2e"}', encoding="utf-8"
    )
    get_settings.cache_clear()
    try:
        st = default_runtime_state(workspace_root=tmp_path / "ws")
        st["project_registry"] = {
            "projects": {
                "e2e": {
                    "project_id": "e2e",
                    "name": "e2e",
                    "aliases": ["e2e"],
                    "repo_path": str(repo.resolve()),
                    "provider_links": [],
                }
            },
            "last_scanned_at": None,
        }
        save_runtime_state(st)

        monkeypatch.setattr(
            "app.deploy_context.context_resolution.probe_provider_session",
            lambda *_a, **_k: {"authenticated": True, "cli_installed": True},
        )
        monkeypatch.setattr("app.deploy_context.context_resolution.detect_cli_path", lambda _pid: "/v/vercel")

        def _fake_fetch(_ctx: dict[str, Any], *, environment: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            return [{"uid": "dep-e2e", "state": "READY", "url": "https://e2e.vercel.app"}], {
                "returncode": 0,
                "failure_category": "ok",
                "summary_lines": [],
                "preview": "",
            }

        monkeypatch.setattr(vercel_actions, "_fetch_deployment_rows", _fake_fetch)

        def _fake_run(argv: list[str], **kwargs: Any) -> tuple[int, str, str]:
            if argv[:2] == ["vercel", "redeploy"]:
                return 0, "https://e2e-new.vercel.app\n", ""
            return 1, "", "err"

        monkeypatch.setattr("app.providers.actions.vercel_actions.run_cli_argv", _fake_run)
        monkeypatch.setattr(vercel_actions, "record_operator_provider_action", lambda *_a, **_k: None)

        from app.deploy_context.context_execution import execute_vercel_redeploy

        out = execute_vercel_redeploy("e2e")
        assert out.get("success") is True
        from app.runtime.runtime_state import load_runtime_state

        st2 = load_runtime_state()
        ident = (st2.get("deployment_identities") or {}).get("e2e")
        assert ident and ident.get("repo_path") == str(repo.resolve())
    finally:
        get_settings.cache_clear()
