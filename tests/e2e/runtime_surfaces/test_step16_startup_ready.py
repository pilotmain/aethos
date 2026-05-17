# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_step16_startup_ready_bounded(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    hdr = {"X-User-Id": uid}
    for path in (
        "/api/v1/runtime/startup",
        "/api/v1/runtime/readiness",
        "/api/v1/runtime/hydration/stages",
        "/api/v1/runtime/bootstrap",
    ):
        r = client.get(path, headers=hdr, timeout=15.0)
        assert r.status_code == 200, path
    caps = client.get("/api/v1/runtime/capabilities", headers=hdr, timeout=10.0)
    assert caps.json().get("mc_compatibility_version") == "phase4_step19"
