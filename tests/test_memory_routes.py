# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient

from app.main import app


def test_legacy_memory_prefix_returns_gone() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/memory", headers={"X-User-Id": "web_deprec_test"})
    assert r.status_code == 410


def test_memory_state_and_forget_routes() -> None:
    client = TestClient(app)
    headers = {"X-User-Id": "web_memory_route_test"}

    remember = client.post(
        "/api/v1/web/memory/remember",
        headers=headers,
        json={"content": "Do not ask me about the report again", "category": "rule"},
    )
    assert remember.status_code == 200, remember.text

    state = client.get("/api/v1/web/memory/state", headers=headers)
    assert state.status_code == 200, state.text
    data = state.json()
    assert "soul_markdown" in data
    assert "memory_markdown" in data
    assert len(data["notes"]) >= 1

    forget = client.post("/api/v1/web/memory/forget", headers=headers, json={"query": "report"})
    assert forget.status_code == 200, forget.text
    forgot = forget.json()
    assert forgot["query"] == "report"
