# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_operational_strategy_flow(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/runtime/strategy", headers={"X-User-Id": uid})
    assert r.status_code == 200
    body = r.json()
    assert "strategic_runtime_alerts" in body or "operational_trajectory_summary" in body
