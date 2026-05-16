# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_enterprise_ecosystem_strategy(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/enterprise/intelligence", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "enterprise_intelligence" in r.json()
