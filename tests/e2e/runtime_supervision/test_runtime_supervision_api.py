# SPDX-License-Identifier: Apache-2.0

from fastapi.testclient import TestClient


def test_runtime_supervision_e2e(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    hdr = {"X-User-Id": uid}
    r = client.get("/api/v1/runtime/supervision", headers=hdr, timeout=15.0)
    assert r.status_code == 200
    assert r.json()["runtime_supervision"]["phase"] == "phase4_step20"
