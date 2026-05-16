# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.gateway.operator_intent_router import execute_provider_nl_intent
from app.gateway.provider_intents import parse_provider_operation_intent
from app.runtime.runtime_state import default_runtime_state, load_runtime_state, save_runtime_state


def test_gateway_nl_records_operator_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
            lambda *_a, **_k: {"authenticated": True, "cli_installed": True},
        )
        monkeypatch.setattr("app.deploy_context.context_resolution.detect_cli_path", lambda _p: "/v/vercel")
        monkeypatch.setattr(
            "app.gateway.operator_intent_router.execute_vercel_status",
            lambda *_a, **_k: {"success": True, "action": "deployment_status", "summary": "state=READY"},
        )

        parsed = parse_provider_operation_intent("check acme production")
        parsed["project_id"] = "acme"
        execute_provider_nl_intent(parsed)

        st2 = load_runtime_state()
        tail = st2.get("operator_provider_actions") or []
        assert any(isinstance(x, dict) and x.get("source") == "gateway_nl" for x in tail)
        hist = st2.get("project_resolution_history") or []
        assert any(isinstance(x, dict) and x.get("source") == "gateway_nl" for x in hist)
    finally:
        get_settings.cache_clear()
