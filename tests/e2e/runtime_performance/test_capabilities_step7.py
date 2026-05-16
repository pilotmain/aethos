# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_runtime_step7_apis(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    hdr = {"X-User-Id": uid}
    for path in (
        "/api/v1/runtime/responsiveness",
        "/api/v1/runtime/throttling",
        "/api/v1/runtime/payloads",
    ):
        r = client.get(path, headers=hdr)
        assert r.status_code == 200
    caps = client.get("/api/v1/runtime/capabilities", headers=hdr)
    assert caps.json().get("mc_compatibility_version") == "phase4_step8"
