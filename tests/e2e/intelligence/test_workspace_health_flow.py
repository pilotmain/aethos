# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient


def test_e2e_operational_intelligence(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/operational-intelligence", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "signals" in r.json()
