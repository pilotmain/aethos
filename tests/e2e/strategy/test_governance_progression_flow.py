# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_governance_progression_flow(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/governance/progression", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "governance_maturity_progression" in r.json()
