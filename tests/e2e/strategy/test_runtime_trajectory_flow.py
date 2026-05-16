# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_runtime_trajectory_flow(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/runtime/trajectory", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "runtime_trajectory" in r.json()
