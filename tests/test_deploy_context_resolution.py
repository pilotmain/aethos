# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.deploy_context.context_resolution import build_deploy_context, resolve_project_for_deploy
from app.deploy_context.errors import ProjectResolutionError
from app.runtime.runtime_state import default_runtime_state, save_runtime_state


def test_resolve_project_for_deploy_unknown_raises(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    get_settings.cache_clear()
    try:
        st = default_runtime_state(workspace_root=tmp_path / "ws")
        save_runtime_state(st)
        with pytest.raises(ProjectResolutionError) as ei:
            resolve_project_for_deploy("nonexistent-xyz-123")
        payload = ei.value.to_payload()
        assert payload.get("suggestions")
    finally:
        get_settings.cache_clear()


def test_build_deploy_context_updates_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    repo = tmp_path / "app"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({"name": "my-app"}), encoding="utf-8")
    (repo / ".git").mkdir()
    vdir = repo / ".vercel"
    vdir.mkdir()
    (vdir / "project.json").write_text(
        json.dumps({"projectId": "p1", "orgId": "o1", "projectName": "my-app"}),
        encoding="utf-8",
    )
    get_settings.cache_clear()
    try:
        st = default_runtime_state(workspace_root=tmp_path / "ws")
        st["project_registry"] = {
            "projects": {
                "my-app": {
                    "project_id": "my-app",
                    "name": "my-app",
                    "aliases": ["my-app"],
                    "repo_path": str(repo.resolve()),
                    "provider_links": [{"provider": "vercel", "project_id": "p1", "project_name": "my-app"}],
                }
            },
            "last_scanned_at": None,
        }
        save_runtime_state(st)

        monkeypatch.setattr(
            "app.deploy_context.context_resolution.probe_provider_session",
            lambda *_a, **_k: {"authenticated": True, "cli_installed": True},
        )
        monkeypatch.setattr("app.deploy_context.context_resolution.detect_cli_path", lambda _pid: "/x/vercel")

        ctx = build_deploy_context("my-app", provider="vercel", environment="production")
        assert ctx["repo_path"] == str(repo.resolve())
        assert ctx["provider"] == "vercel"

        from app.runtime.runtime_state import load_runtime_state

        st2 = load_runtime_state()
        cache = st2.get("provider_resolution_cache") or {}
        assert "my-app" in cache
    finally:
        get_settings.cache_clear()
