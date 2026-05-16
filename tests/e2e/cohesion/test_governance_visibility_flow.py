# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient


def test_e2e_runtime_timeline(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/runtime/timeline", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "timeline" in r.json()
