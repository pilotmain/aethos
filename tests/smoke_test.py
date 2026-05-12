# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient

from app.main import app


def test_full_flow():
    client = TestClient(app)
    headers = {"X-User-Id": "test_user"}

    r = client.get("/api/v1/health")
    assert r.status_code == 200

    r = client.post(
        "/api/v1/plans/generate",
        headers=headers,
        json={"text": "finish report, call mom, gym tomorrow, book flight"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["extracted_tasks_count"] >= 3

    r = client.get("/api/v1/tasks", headers=headers)
    assert r.status_code == 200
    tasks = r.json()
    assert len(tasks) >= 3

    task_id = tasks[0]["id"]
    r = client.post(f"/api/v1/tasks/{task_id}/complete", headers=headers)
    assert r.status_code == 200

    r = client.get("/api/v1/checkins/pending", headers=headers)
    assert r.status_code == 200
