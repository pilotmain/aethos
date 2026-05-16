# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.runtime.runtime_state import default_runtime_state, save_runtime_state


def test_providers_list_from_runtime_state(api_client, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    get_settings.cache_clear()
    try:
        st = default_runtime_state(workspace_root=tmp_path / "ws")
        st["provider_inventory"]["providers"]["vercel"] = {
            "provider": "vercel",
            "cli_installed": True,
            "cli_path": "/mock/vercel",
            "authenticated": False,
            "auth_source": "local_cli",
            "project_count": 0,
        }
        save_runtime_state(st)
        client, _ = api_client
        r = client.get("/api/v1/providers/")
        assert r.status_code == 200
        body = r.json()
        assert body["providers"]["vercel"]["cli_installed"] is True
    finally:
        get_settings.cache_clear()


def test_providers_scan_uses_service(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.routes import providers_api

    def _fake_scan(*, persist: bool = True):
        return {
            "providers": {"github": {"provider": "github", "cli_installed": True}},
            "last_scanned_at": "2099-01-01T00:00:00Z",
        }

    monkeypatch.setattr(providers_api, "scan_providers_inventory", _fake_scan)
    client, _ = api_client
    r = client.post("/api/v1/providers/scan")
    assert r.status_code == 200
    assert r.json()["providers"]["github"]["cli_installed"] is True


def test_providers_show_unknown_404(api_client) -> None:
    client, _ = api_client
    assert client.get("/api/v1/providers/not_a_provider").status_code == 404


def test_providers_non_vercel_projects_empty(api_client) -> None:
    client, _ = api_client
    r = client.get("/api/v1/providers/railway/projects")
    assert r.status_code == 200
    assert r.json().get("projects") == []


def test_projects_link_and_show(api_client, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "ahome"
    home.mkdir()
    monkeypatch.setenv("AETHOS_HOME_DIR", str(home))
    get_settings.cache_clear()
    try:
        st = default_runtime_state(workspace_root=tmp_path / "ws")
        save_runtime_state(st)
        client, _ = api_client
        repo = tmp_path / "myrepo"
        repo.mkdir()
        lr = client.post("/api/v1/projects/acme/link", json={"repo_path": str(repo)})
        assert lr.status_code == 200
        gr = client.get("/api/v1/projects/acme")
        assert gr.status_code == 200
        assert gr.json().get("repo_path") == str(repo)
    finally:
        get_settings.cache_clear()
