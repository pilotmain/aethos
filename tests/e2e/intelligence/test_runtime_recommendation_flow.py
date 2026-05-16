# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient


def test_e2e_recommendations(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/runtime-recommendations", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "recommendations" in r.json()
