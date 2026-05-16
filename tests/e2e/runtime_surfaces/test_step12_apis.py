# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_step12_runtime_apis(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    hdr = {"X-User-Id": uid}
    for path in (
        "/api/v1/runtime/routing/history",
        "/api/v1/runtime/routing/explanations",
        "/api/v1/runtime/providers/health-matrix",
        "/api/v1/runtime/perception",
        "/api/v1/runtime/operator-experience",
    ):
        r = client.get(path, headers=hdr)
        assert r.status_code == 200, path
    caps = client.get("/api/v1/runtime/capabilities", headers=hdr)
    assert caps.json().get("mc_compatibility_version") == "phase4_step12"
