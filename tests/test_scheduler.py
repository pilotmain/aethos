# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 22 — scheduler API + persisted jobs."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.nexa_scheduler_job import NexaSchedulerJob
from app.core.security import get_valid_web_user_id


def test_scheduler_create_list_delete(db_session, monkeypatch) -> None:
    uid = f"web_sched_{__import__('uuid').uuid4().hex[:10]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)

    c = TestClient(app)
    try:
        r = c.post(
            "/api/v1/scheduler/create",
            headers={"X-User-Id": uid},
            json={
                "mission_text": "@researcher: weekly digest test body",
                "kind": "interval",
                "interval_seconds": 3600,
                "label": "test job",
            },
        )
        assert r.status_code == 200
        jid = r.json()["id"]
        row = db_session.get(NexaSchedulerJob, jid)
        assert row is not None
        assert row.user_id == uid

        lst = c.get("/api/v1/scheduler/list", headers={"X-User-Id": uid})
        assert lst.status_code == 200
        jobs = lst.json().get("jobs") or []
        assert any(j.get("id") == jid for j in jobs)

        d = c.delete(f"/api/v1/scheduler/{jid}", headers={"X-User-Id": uid})
        assert d.status_code == 200
        db_session.expire_all()
        assert db_session.get(NexaSchedulerJob, jid) is None
    finally:
        app.dependency_overrides.clear()
