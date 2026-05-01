from fastapi.testclient import TestClient

from app.main import app


def test_memory_state_and_forget_routes() -> None:
    client = TestClient(app)
    headers = {"X-User-Id": "memory_route_user"}

    remember = client.post(
        "/api/v1/memory/remember",
        headers=headers,
        json={"content": "Do not ask me about the report again", "category": "rule"},
    )
    assert remember.status_code == 200, remember.text

    state = client.get("/api/v1/memory/state", headers=headers)
    assert state.status_code == 200, state.text
    data = state.json()
    assert "soul_markdown" in data
    assert "memory_markdown" in data
    assert len(data["notes"]) >= 1

    forget = client.post("/api/v1/memory/forget", headers=headers, json={"query": "report"})
    assert forget.status_code == 200, forget.text
    forgot = forget.json()
    assert forgot["query"] == "report"
