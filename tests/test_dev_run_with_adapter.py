# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 24 — dev run records adapter."""

from __future__ import annotations

import subprocess

from fastapi.testclient import TestClient

from app.core.security import get_valid_web_user_id
from app.main import app


def test_dev_run_records_adapter_used(db_session, tmp_path, monkeypatch) -> None:
    repo = tmp_path / "adev_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    uid = f"web_adapter_{__import__('uuid').uuid4().hex[:10]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
    monkeypatch.setenv("NEXA_AIDER_ENABLED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    c = TestClient(app)
    try:
        w = c.post(
            "/api/v1/dev/workspaces",
            headers={"X-User-Id": uid},
            json={"name": "adev", "repo_path": str(repo)},
        )
        assert w.status_code == 200
        wid = w.json()["workspace"]["id"]

        r = c.post(
            "/api/v1/dev/runs",
            headers={"X-User-Id": uid},
            json={
                "workspace_id": wid,
                "goal": "hello adapter",
                "preferred_agent": "local_stub",
                "allow_write": False,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("adapter_used") == "local_stub"

        rid = body["run_id"]
        gr = c.get(f"/api/v1/dev/runs/{rid}", headers={"X-User-Id": uid})
        assert gr.status_code == 200
        rj = gr.json()["run"].get("result_json") or {}
        assert rj.get("adapter_used") == "local_stub"
    finally:
        app.dependency_overrides.clear()
        monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
        get_settings.cache_clear()
