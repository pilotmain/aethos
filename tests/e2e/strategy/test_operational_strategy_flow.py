# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_operational_strategy_flow(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/enterprise/strategy", headers={"X-User-Id": uid})
    assert r.status_code == 200
    body = r.json()
    assert "runtime_maturity_strategy" in body or "resilience_strategy" in body
