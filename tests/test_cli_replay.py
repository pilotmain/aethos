"""Phase 21 — mission replay API used by CLI."""

from __future__ import annotations

import uuid

from app.models.nexa_next_runtime import NexaMission
from app.main import app
from fastapi.testclient import TestClient


def test_replay_mission_endpoint_returns_payload(db_session, monkeypatch) -> None:
    from app.core.security import get_valid_web_user_id

    uid = f"replay_u_{uuid.uuid4().hex[:8]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)

    mid = str(uuid.uuid4())
    db_session.add(
        NexaMission(
            id=mid,
            user_id=uid,
            title="t",
            status="completed",
            input_text="goal: test replay body",
        )
    )
    db_session.commit()

    try:
        c = TestClient(app)
        r = c.post(f"/api/v1/mission-control/replay/{mid}", headers={"X-User-Id": uid})
        assert r.status_code == 200
        body = r.json()
        assert body.get("mode") in ("chat", None) or body.get("status") is not None
    finally:
        app.dependency_overrides.clear()
