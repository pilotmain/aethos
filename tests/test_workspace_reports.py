"""Report watcher API and safe report file reads."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import get_valid_web_user_id
from app.main import app
from app.services.agent_runtime.paths import reports_dir
from app.services.agent_runtime.workspace_files import ensure_seed_files, safe_read_report_file


@pytest.fixture
def api_client(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    uid = f"rw_{uuid.uuid4().hex[:10]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    try:
        yield TestClient(app), uid, tmp_path
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_safe_read_rejects_traversal(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_AGENT_TOOLS_ENABLED", "true")
    get_settings.cache_clear()
    ensure_seed_files()
    assert safe_read_report_file("../etc/passwd") is None
    assert safe_read_report_file("mission_control.md") is not None


def test_reports_status_and_mission_control(api_client) -> None:
    client, _uid, tmp_path = api_client
    ensure_seed_files()
    r = client.get("/api/v1/reports/status")
    assert r.status_code == 200
    body = r.json()
    assert "mission_control_mtime" in body
    assert str(tmp_path) in body.get("reports_dir", "") or reports_dir().exists()

    r2 = client.get("/api/v1/reports/mission-control")
    assert r2.status_code == 200
    assert "markdown" in r2.json()
