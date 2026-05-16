# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.runtime.runtime_state import default_runtime_state, save_runtime_state


def test_gateway_run_restart_invoicepilot_mocked(
    api_client,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    get_settings.cache_clear()
    try:
        repo = tmp_path / "app"
        repo.mkdir()
        (repo / "package.json").write_text(json.dumps({"name": "invoicepilot"}), encoding="utf-8")
        (repo / ".vercel").mkdir()
        (repo / ".vercel" / "project.json").write_text(
            json.dumps({"projectId": "p1", "orgId": "o1"}), encoding="utf-8"
        )
        st = default_runtime_state(workspace_root=tmp_path / "ws")
        st["project_registry"] = {
            "projects": {
                "invoicepilot": {
                    "project_id": "invoicepilot",
                    "name": "invoicepilot",
                    "aliases": ["invoicepilot"],
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

        def _fake_restart(slug: str, *, environment: str = "production"):
            return {
                "provider": "vercel",
                "action": "restart_project",
                "success": True,
                "project": slug,
                "url": "https://invoicepilot.vercel.app",
            }

        monkeypatch.setattr(
            "app.gateway.operator_intent_router.execute_vercel_restart",
            _fake_restart,
        )

        client, uid = api_client
        r = client.post(
            "/api/v1/mission-control/gateway/run",
            json={"text": "restart invoicepilot", "user_id": uid},
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("provider_operation") is True
        assert "invoicepilot" in (body.get("text") or "").lower()
    finally:
        get_settings.cache_clear()
