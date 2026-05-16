# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.runtime.runtime_state import default_runtime_state, load_runtime_state, save_runtime_state


def test_fix_and_redeploy_persists_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    repo = tmp_path / "app"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({"scripts": {"build": "echo ok"}}), encoding="utf-8")
    (repo / ".vercel").mkdir()
    (repo / ".vercel" / "project.json").write_text(
        json.dumps({"projectId": "p1", "orgId": "o1"}), encoding="utf-8"
    )
    get_settings.cache_clear()
    try:
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
            lambda *_a, **_k: {"authenticated": True},
        )
        monkeypatch.setattr("app.deploy_context.context_resolution.detect_cli_path", lambda _p: "/v")
        monkeypatch.setattr(
            "app.providers.repair.fix_and_redeploy.execute_vercel_logs",
            lambda *_a, **_k: {"success": True, "summary": "ok", "extra": {"cli": {"preview": "build failed"}}},
        )
        monkeypatch.setattr(
            "app.providers.repair.repair_execution.run_verification_suite",
            lambda _p: {"ok": True, "results": []},
        )
        monkeypatch.setattr(
            "app.providers.repair.repair_execution._run_shell",
            lambda cmd, cwd, **kw: {"ok": True, "command": cmd, "returncode": 0, "cli": {"preview": ""}},
        )
        monkeypatch.setattr(
            "app.providers.repair.fix_and_redeploy.execute_vercel_redeploy",
            lambda *_a, **_k: {"success": True, "action": "redeploy_latest", "url": "https://a.vercel.app"},
        )
        from app.providers.repair.fix_and_redeploy import run_fix_and_redeploy

        run_fix_and_redeploy("acme", source="test")
        st2 = load_runtime_state()
        plans = (st2.get("execution") or {}).get("plans") or {}
        assert isinstance(plans, dict) and len(plans) >= 1
        assert (st2.get("repair_contexts") or {}).get("latest_by_project", {}).get("acme")
    finally:
        get_settings.cache_clear()
