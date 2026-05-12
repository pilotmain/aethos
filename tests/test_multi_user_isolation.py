# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 20 — missions and exports scoped by user_id."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.core import config as cfg
from app.main import app
from app.models.nexa_next_runtime import NexaMission


def test_export_other_users_mission_returns_404(db_session, monkeypatch) -> None:
    from app.core.security import get_valid_web_user_id

    owner = f"owner_{uuid.uuid4().hex[:8]}"
    intruder = f"other_{uuid.uuid4().hex[:8]}"
    mid = str(uuid.uuid4())
    db_session.add(
        NexaMission(
            id=mid,
            user_id=owner,
            title="Private",
            status="running",
            input_text=None,
        )
    )
    db_session.commit()

    app.dependency_overrides[get_valid_web_user_id] = lambda: intruder
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
    cfg.get_settings.cache_clear()
    try:
        c = TestClient(app)
        r = c.get(f"/api/v1/mission-control/export/{mid}", headers={"X-User-Id": intruder})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()
        cfg.get_settings.cache_clear()


def test_execution_snapshot_filters_streams_by_user_id(db_session, monkeypatch) -> None:
    from app.services.mission_control.nexa_next_state import STATE, build_execution_snapshot

    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
    cfg.get_settings.cache_clear()
    u1 = "stream_u1"
    u2 = "stream_u2"
    STATE.setdefault("provider_events", []).clear()
    STATE["provider_events"].append({"provider": "local_stub", "status": "completed", "user_id": u1})
    STATE["provider_events"].append({"provider": "local_stub", "status": "completed", "user_id": u2})

    snap_all = build_execution_snapshot(db_session, user_id=None)
    assert len(snap_all["provider_events"]) == 2

    snap1 = build_execution_snapshot(db_session, user_id=u1)
    assert len(snap1["provider_events"]) == 1
    assert snap1["provider_events"][0].get("user_id") == u1

    STATE["provider_events"].clear()
