# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_step16_setup_and_runtime_apis(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    hdr = {"X-User-Id": uid}
    for path in (
        "/api/v1/setup/doctor",
        "/api/v1/runtime/startup",
        "/api/v1/runtime/readiness",
        "/api/v1/runtime/bootstrap",
        "/api/v1/runtime/compatibility",
        "/api/v1/runtime/branding-audit",
    ):
        r = client.get(path, headers=hdr if path.startswith("/api/v1/runtime") else None)
        assert r.status_code == 200, path
    caps = client.get("/api/v1/runtime/capabilities", headers=hdr)
    assert caps.json().get("mc_compatibility_version") == "phase4_step18"
