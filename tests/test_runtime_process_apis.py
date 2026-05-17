# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_runtime_process_apis(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    hdr = {"X-User-Id": uid}
    for path in (
        "/api/v1/runtime/ownership",
        "/api/v1/runtime/services",
        "/api/v1/runtime/processes",
        "/api/v1/runtime/db-health",
        "/api/v1/runtime/startup-lock",
    ):
        r = client.get(path, headers=hdr)
        assert r.status_code == 200, path
    caps = client.get("/api/v1/runtime/capabilities", headers=hdr)
    assert caps.json().get("mc_compatibility_version") == "phase4_step18"
