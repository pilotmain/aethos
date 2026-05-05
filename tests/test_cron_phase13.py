"""Phase 13 — cron job store + HTTP API."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.services.cron.job_store import CronJobStore
from app.services.cron.models import CronJob, JobActionType, JobStatus


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def store(tmp_path: Path) -> CronJobStore:
    return CronJobStore(tmp_path / "t.sqlite")


def test_job_store_roundtrip(store: CronJobStore) -> None:
    j = CronJob(
        id="abc123",
        name="t",
        cron_expression="0 * * * *",
        action_type=JobActionType.CHANNEL_MESSAGE,
        action_payload={"channel": "telegram", "chat_id": "1", "message": "hi"},
    )
    store.save(j)
    got = store.get("abc123")
    assert got is not None
    assert got.cron_expression == "0 * * * *"
    assert len(store.list_all()) == 1
    assert store.delete("abc123")
    assert store.get("abc123") is None


def test_cron_api_requires_token_configured_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """When NEXA_CRON_API_TOKEN is unset/empty, verify_cron_token returns 503."""
    monkeypatch.setenv("NEXA_CRON_API_TOKEN", "")
    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    r = c.get("/api/v1/cron/jobs")
    assert r.status_code == 503


def test_cron_api_with_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_CRON_API_TOKEN", "testtok-cron-secret")
    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import app

    c = TestClient(app)
    r = c.get(
        "/api/v1/cron/jobs",
        headers={"Authorization": "Bearer testtok-cron-secret"},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True
