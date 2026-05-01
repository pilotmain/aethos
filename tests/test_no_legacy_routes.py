"""Phase 26 — agents alias and route sanity (no duplicate legacy surface in tests)."""

from __future__ import annotations


def test_agents_endpoint_matches_custom_agents_list(api_client) -> None:
    client, _uid = api_client
    a = client.get("/api/v1/agents")
    b = client.get("/api/v1/custom-agents")
    assert a.status_code == 200
    assert b.status_code == 200
    assert a.json() == b.json()
