"""Phase 23 — HTTP API for workspaces + runs."""

from __future__ import annotations

import subprocess

from fastapi.testclient import TestClient

from app.core.security import get_valid_web_user_id
from app.main import app


def test_dev_workspaces_and_runs_api(db_session, tmp_path, monkeypatch) -> None:
    repo = tmp_path / "api_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    uid = f"web_devapi_{__import__('uuid').uuid4().hex[:10]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    c = TestClient(app)
    try:
        w = c.post(
            "/api/v1/dev/workspaces",
            headers={"X-User-Id": uid},
            json={"name": "api", "repo_path": str(repo)},
        )
        assert w.status_code == 200
        wid = w.json()["workspace"]["id"]

        r = c.post(
            "/api/v1/dev/runs",
            headers={"X-User-Id": uid},
            json={"workspace_id": wid, "goal": "hello", "auto_pr": False},
        )
        assert r.status_code == 200
        assert r.json().get("ok") is True

        lst = c.get("/api/v1/dev/workspaces", headers={"X-User-Id": uid})
        assert lst.status_code == 200
        assert len(lst.json().get("workspaces") or []) >= 1
    finally:
        app.dependency_overrides.clear()
        monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
        get_settings.cache_clear()
