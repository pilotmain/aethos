# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""REST API for custom agents (Phase 20)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal, ensure_schema
from app.core.security import get_valid_web_user_id
from app.api.routes import custom_agents_api as ca_api
from app.main import app
from app.models.audit_log import AuditLog


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch):
    ensure_schema()
    uid = f"web_{uuid.uuid4().hex[:12]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    monkeypatch.setattr(
        ca_api,
        "can_user_create_custom_agents",
        lambda _db, _u: (True, None),
    )
    try:
        yield TestClient(app), uid
    finally:
        app.dependency_overrides.clear()


def test_custom_agents_crud(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    h = uuid.uuid4().hex[:8]
    handle = f"api_agent_{h}"

    r0 = client.get("/api/v1/custom-agents")
    assert r0.status_code == 200
    assert r0.json()["agents"] == []

    prompt = (
        f"Create me a custom agent called @{handle}. "
        "It helps summarize meeting notes. Skills: summarization."
    )
    r1 = client.post("/api/v1/custom-agents", json={"prompt": prompt})
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert body["ok"] is True
    assert body["agent"]["handle"] == handle
    assert body["agent"]["enabled"] is True

    r2 = client.get(f"/api/v1/custom-agents/{handle}")
    assert r2.status_code == 200
    det = r2.json()
    assert det["handle"] == handle
    assert "instructions_preview" in det
    assert len(det["instructions_preview"]) > 10

    r3 = client.get("/api/v1/custom-agents")
    assert r3.status_code == 200
    agents = r3.json()["agents"]
    assert len(agents) >= 1
    assert any(a["handle"] == handle for a in agents)

    r4 = client.patch(
        f"/api/v1/custom-agents/{handle}",
        json={"enabled": False, "description": "Updated via API"},
    )
    assert r4.status_code == 200
    assert r4.json()["enabled"] is False
    assert "API" in r4.json()["description"]

    r5 = client.delete(f"/api/v1/custom-agents/{handle}")
    assert r5.status_code == 204

    r6 = client.get(f"/api/v1/custom-agents/{handle}")
    assert r6.status_code == 200
    assert r6.json()["enabled"] is False


def test_create_invalid_returns_400(api_client: tuple[TestClient, str]) -> None:
    client, _uid = api_client
    r = client.post("/api/v1/custom-agents", json={"prompt": "hello there"})
    assert r.status_code == 400


def test_patch_audit_has_metadata(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    h = uuid.uuid4().hex[:8]
    handle = f"patch_audit_{h}"
    client.post(
        "/api/v1/custom-agents",
        json={
            "prompt": f"Create me a custom agent called @{handle}. Role: tester.",
        },
    )
    client.patch(f"/api/v1/custom-agents/{handle}", json={"description": "x"})
    db = SessionLocal()
    try:
        rows = (
            db.query(AuditLog)
            .filter(
                AuditLog.user_id == uid,
                AuditLog.event_type == "custom_agent.updated",
            )
            .order_by(AuditLog.id.desc())
            .limit(3)
            .all()
        )
        assert rows
        meta = rows[0].metadata_json or {}
        assert meta.get("handle") == handle
        assert meta.get("source") == "api"
    finally:
        db.close()
