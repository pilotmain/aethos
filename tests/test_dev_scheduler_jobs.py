# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 24 — scheduler dev_mission payload."""

from __future__ import annotations

import json

from app.services.scheduler.dev_jobs import execute_dev_mission_job, parse_dev_mission_payload


def test_parse_dev_mission() -> None:
    raw = json.dumps(
        {"type": "dev_mission", "workspace_id": "w", "goal": "g", "preferred_agent": "local_stub"}
    )
    p = parse_dev_mission_payload(raw)
    assert p is not None
    assert p["type"] == "dev_mission"


def test_parse_non_json_returns_none() -> None:
    assert parse_dev_mission_payload("hello world") is None


def test_execute_dev_mission_dispatches(db_session, tmp_path, monkeypatch) -> None:
    import subprocess
    import uuid

    from app.models.nexa_scheduler_job import NexaSchedulerJob

    repo = tmp_path / "sched_dev"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    uid = f"sched_u_{__import__('uuid').uuid4().hex[:8]}"
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
    from app.core.config import get_settings
    from app.models.dev_runtime import NexaDevWorkspace
    from app.main import app
    from fastapi.testclient import TestClient
    from app.core.security import get_valid_web_user_id

    get_settings.cache_clear()
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    c = TestClient(app)
    w = c.post(
        "/api/v1/dev/workspaces",
        headers={"X-User-Id": uid},
        json={"name": "s", "repo_path": str(repo)},
    )
    wid = w.json()["workspace"]["id"]

    payload = {
        "type": "dev_mission",
        "workspace_id": wid,
        "goal": "scheduled probe",
        "preferred_agent": "local_stub",
        "allow_write": False,
    }
    row = NexaSchedulerJob(
        id=str(uuid.uuid4()),
        user_id=uid,
        label="t",
        mission_text=json.dumps(payload),
        kind="interval",
        interval_seconds=3600,
        enabled=True,
    )
    db_session.add(row)
    db_session.commit()

    handled = execute_dev_mission_job(db_session, row)
    assert handled is True

    from sqlalchemy import select
    from app.models.dev_runtime import NexaDevRun

    runs = list(db_session.scalars(select(NexaDevRun).where(NexaDevRun.user_id == uid)).all())
    assert any("scheduled probe" in (x.goal or "") for x in runs)

    app.dependency_overrides.clear()
    monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
    get_settings.cache_clear()
