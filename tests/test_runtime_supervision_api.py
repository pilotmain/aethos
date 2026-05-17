# SPDX-License-Identifier: Apache-2.0

from fastapi.testclient import TestClient


def test_runtime_supervision_api(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    hdr = {"X-User-Id": uid}
    r = client.get("/api/v1/runtime/supervision", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert "runtime_supervision" in body
    assert body["runtime_supervision"]["phase"] == "phase4_step20"
