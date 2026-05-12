# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 30 — mobile API (JWT + Mission Control scoped to mobile:{user_id})."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mobile_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_SECRET_KEY", "unit-test-mobile-jwt-secret-key-32bytes!")


@pytest.fixture
def client(mobile_secret: None) -> TestClient:
    from app.main import app

    return TestClient(app)


def test_mobile_login_me_and_org_projects(client: TestClient) -> None:
    r = client.post(
        "/api/v1/mobile/auth/login",
        json={"user_id": "telegram-123", "user_name": "Tester"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("token")
    token = body["token"]
    auth = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/v1/mobile/me", headers=auth)
    assert me.status_code == 200
    assert me.json()["user_id"] == "telegram-123"

    co = client.post(
        "/api/v1/mobile/orgs",
        json={"name": "Mobile Co"},
        headers=auth,
    )
    assert co.status_code == 200
    org_id = co.json()["organization"]["id"]

    active = client.post(f"/api/v1/mobile/orgs/{org_id}/active", headers=auth)
    assert active.status_code == 200

    pr = client.post(
        "/api/v1/mobile/projects",
        json={
            "name": "Ship app",
            "goal": "Launch Nexa mobile",
            "organization_id": org_id,
        },
        headers=auth,
    )
    assert pr.status_code == 200
    pid = pr.json()["project"]["id"]

    lst = client.get(f"/api/v1/mobile/orgs/{org_id}/projects", headers=auth)
    assert lst.status_code == 200
    ids = {p["id"] for p in lst.json()["projects"]}
    assert pid in ids

    tree = client.get(f"/api/v1/mobile/projects/{pid}/tree", headers=auth)
    assert tree.status_code == 200
    tj = tree.json()
    assert "project" in tj
    assert "items" in tj["tasks"]

    tk = client.post(
        "/api/v1/mobile/tasks",
        json={"title": "Kanban task", "project_id": pid},
        headers=auth,
    )
    assert tk.status_code == 200
    tid = tk.json()["task"]["id"]

    tree_after = client.get(f"/api/v1/mobile/projects/{pid}/tree", headers=auth)
    assert tree_after.status_code == 200
    assert len(tree_after.json()["tasks"]["items"]) >= 1

    patch = client.patch(
        f"/api/v1/mobile/tasks/{tid}",
        json={"status": "in_progress"},
        headers=auth,
    )
    assert patch.status_code == 200
    assert patch.json()["task"]["status"] == "in_progress"

    dash = client.get("/api/v1/mobile/dashboard", headers=auth)
    assert dash.status_code == 200
    assert "recent_tasks" in dash.json()

    sync = client.get("/api/v1/mobile/sync", headers=auth)
    assert sync.status_code == 200
    assert "projects" in sync.json() and "tasks" in sync.json()

    reg = client.post(
        "/api/v1/mobile/push-token",
        json={"push_token": "test-device-token", "platform": "ios"},
        headers=auth,
    )
    assert reg.status_code == 200
    assert reg.json().get("ok") is True
