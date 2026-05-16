# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.gateway.operator_intent_router import execute_provider_nl_intent
from app.gateway.provider_intents import parse_provider_operation_intent
from app.runtime.runtime_state import default_runtime_state, save_runtime_state


def test_nl_missing_auth_clean_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    get_settings.cache_clear()
    try:
        repo = tmp_path / "app"
        repo.mkdir()
        (repo / "package.json").write_text("{}", encoding="utf-8")
        (repo / ".vercel").mkdir()
        (repo / ".vercel" / "project.json").write_text("{}", encoding="utf-8")
        st = default_runtime_state(workspace_root=tmp_path / "ws")
        st["project_registry"] = {
            "projects": {
                "acme": {
                    "project_id": "acme",
                    "name": "acme",
                    "aliases": ["acme"],
                    "repo_path": str(repo.resolve()),
                    "provider_links": [],
                }
            },
            "last_scanned_at": None,
        }
        save_runtime_state(st)

        monkeypatch.setattr(
            "app.deploy_context.context_resolution.probe_provider_session",
            lambda *_a, **_k: {"authenticated": False, "cli_installed": True},
        )
        monkeypatch.setattr("app.deploy_context.context_resolution.detect_cli_path", lambda _p: "/v/vercel")

        parsed = parse_provider_operation_intent("restart acme")
        assert parsed and parsed.get("project_id") == "acme"
        out = execute_provider_nl_intent(parsed)
        assert "vercel login" in (out.get("text") or "").lower()
        assert "npm" not in (out.get("text") or "").lower() or "enoent" not in (out.get("text") or "").lower()
    finally:
        get_settings.cache_clear()
