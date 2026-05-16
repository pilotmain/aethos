# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_operational_maturity_flow(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/runtime/maturity", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "operational_maturity_scores" in r.json() or "enterprise_operational_posture" in r.json()
