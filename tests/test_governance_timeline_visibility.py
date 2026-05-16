# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.runtime_governance import build_governance_timeline


def test_governance_timeline_human_readable() -> None:
    g = build_governance_timeline(limit=8)
    assert "timeline" in g
    for row in g.get("timeline") or []:
        assert "what" in row
        assert "kind" in row


def test_mc_governance_api_returns_timeline(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/governance", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "timeline" in r.json()
