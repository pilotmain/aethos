"""Phase 23 — dev runs surface on Mission Control snapshot."""

from __future__ import annotations

import subprocess

from fastapi.testclient import TestClient

from app.core.security import get_valid_web_user_id
from app.main import app
from app.services.mission_control.nexa_next_state import build_execution_snapshot


def test_dev_runs_in_mission_control_state(db_session, tmp_path, monkeypatch) -> None:
    repo = tmp_path / "mc_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    uid = f"web_mcdev_{__import__('uuid').uuid4().hex[:10]}"
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
            json={"name": "mc", "repo_path": str(repo)},
        )
        wid = w.json()["workspace"]["id"]
        c.post(
            "/api/v1/dev/runs",
            headers={"X-User-Id": uid},
            json={"workspace_id": wid, "goal": "state test", "auto_pr": False},
        )

        snap = build_execution_snapshot(db_session, user_id=uid)
        assert "dev_runs" in snap
        assert "dev_workspaces" in snap
        assert isinstance(snap["dev_runs"], list)
        assert any("state test" in str(x.get("goal", "")) for x in snap["dev_runs"])
    finally:
        app.dependency_overrides.clear()
        monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
        get_settings.cache_clear()
