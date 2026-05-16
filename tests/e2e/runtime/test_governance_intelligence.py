# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_governance_intelligence_step5_api(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/governance/intelligence", headers={"X-User-Id": uid})
    assert r.status_code == 200
    body = r.json()
    assert "governance_intelligence" in body
