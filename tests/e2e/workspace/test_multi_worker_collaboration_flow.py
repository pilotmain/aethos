# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient


def test_e2e_worker_collaboration(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/worker-collaboration", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "chains" in r.json()
