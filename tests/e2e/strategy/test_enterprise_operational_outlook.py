# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_enterprise_operational_outlook(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/runtime/outlook", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "enterprise_operational_outlook" in r.json()
