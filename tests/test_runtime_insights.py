# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient


def test_runtime_insights_api(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/runtime-insights", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "runtime_insights" in r.json()
