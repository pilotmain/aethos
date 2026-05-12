# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 20 — mission export / import."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.core import config as cfg
from app.main import app
from app.models.nexa_next_runtime import NexaArtifact, NexaMission, NexaMissionTask


def test_export_import_roundtrip(db_session, monkeypatch) -> None:
    from app.core.security import get_valid_web_user_id

    uid = f"mc_export_{uuid.uuid4().hex[:8]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)
    cfg.get_settings.cache_clear()
    mid = str(uuid.uuid4())
    db_session.add(
        NexaMission(
            id=mid,
            user_id=uid,
            title="Export me",
            status="completed",
            input_text="hello",
        )
    )
    db_session.add(
        NexaMissionTask(
            mission_id=mid,
            agent_handle="a1",
            role="worker",
            task="do thing",
            status="completed",
            depends_on=[],
        )
    )
    db_session.add(NexaArtifact(mission_id=mid, agent_handle="a1", artifact_json={"x": 1}))
    db_session.commit()

    try:
        c = TestClient(app)
        ex = c.get(f"/api/v1/mission-control/export/{mid}", headers={"X-User-Id": uid})
        assert ex.status_code == 200
        bundle = ex.json()
        assert bundle["mission"]["title"] == "Export me"
        assert bundle["version"] == 1

        imp = c.post(
            "/api/v1/mission-control/import",
            headers={"X-User-Id": uid},
            json=bundle,
        )
        assert imp.status_code == 200
        new_id = imp.json()["mission_id"]
        assert new_id != mid
        m2 = db_session.get(NexaMission, new_id)
        assert m2 is not None
        assert m2.user_id == uid
    finally:
        app.dependency_overrides.clear()
        cfg.get_settings.cache_clear()
