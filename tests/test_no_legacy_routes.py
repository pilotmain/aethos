"""Phase 27 — /agents duplicate alias removed (use /custom-agents only)."""

from __future__ import annotations


def test_custom_agents_list_ok(api_client) -> None:
    client, _uid = api_client
    r = client.get("/api/v1/custom-agents")
    assert r.status_code == 200
    assert "agents" in r.json()
