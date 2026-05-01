"""Web system status exposes host executor panel (safe fields only)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


@patch("app.core.config.get_settings")
def test_web_system_status_includes_host_executor_panel(mock_gs) -> None:
    mock_gs.return_value = SimpleNamespace(
        app_name="nexa",
        nexa_web_search_enabled=False,
        nexa_web_search_provider="",
        nexa_web_search_api_key="",
        nexa_web_access_enabled=True,
        nexa_browser_preview_enabled=False,
        nexa_host_executor_enabled=True,
        host_executor_work_root="",
        host_executor_timeout_seconds=120,
        host_executor_max_file_bytes=262_144,
    )

    c = TestClient(app)
    r = c.get("/api/v1/web/system/status", headers={"X-User-Id": "web_smoke_1"})
    assert r.status_code == 200, r.text
    data = r.json()
    he = data.get("host_executor")
    assert he is not None
    assert "enabled" in he
    assert "work_root" in he
    assert isinstance(he.get("allowed_host_actions"), list)
    assert isinstance(he.get("allowed_run_names"), list)
    assert "timeout_seconds" in he
    assert "max_file_bytes" in he
