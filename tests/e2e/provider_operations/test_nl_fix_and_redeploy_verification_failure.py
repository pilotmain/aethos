# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.runtime.runtime_state import default_runtime_state, save_runtime_state


def test_verification_failure_blocks_redeploy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    repo = tmp_path / "app"
    repo.mkdir()
    (repo / "package.json").write_text("{}", encoding="utf-8")
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
                    "aliases": ["acme"],
                    "repo_path": str(repo.resolve()),
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
            lambda *_a, **_k: {"success": True, "summary": "fail", "extra": {"cli": {"preview": "npm err"}}},
        )
        monkeypatch.setattr(
            "app.providers.repair.repair_execution.execute_repair_plan",
            lambda *_a, **_k: {
                "ok": False,
                "blocked_reason": "verification_failed",
                "failed_command": "npm run build",
            },
        )
        redeploy_called = {"n": 0}

        def _no_redeploy(*_a, **_k):
            redeploy_called["n"] += 1
            return {"success": True}

        monkeypatch.setattr("app.providers.repair.fix_and_redeploy.execute_vercel_redeploy", _no_redeploy)
        from app.providers.repair.fix_and_redeploy import run_fix_and_redeploy

        out = run_fix_and_redeploy("acme")
        assert out.get("success") is False
        assert redeploy_called["n"] == 0
        assert "not" in (out.get("summary") or "").lower()
    finally:
        get_settings.cache_clear()
