# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_runtime_capabilities(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/runtime/capabilities", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert r.json().get("mc_compatibility_version") == "phase4_step7"


def test_runtime_recovery_center_api(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/runtime-recovery", headers={"X-User-Id": uid})
    assert r.status_code == 200
