# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_step13_runtime_apis(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    hdr = {"X-User-Id": uid}
    for path in (
        "/api/v1/runtime/operational-focus",
        "/api/v1/runtime/priority-work",
        "/api/v1/runtime/noise-reduction",
        "/api/v1/runtime/calmness-metrics",
        "/api/v1/runtime/signal-health",
        "/api/v1/runtime/launch-certification",
    ):
        r = client.get(path, headers=hdr)
        assert r.status_code == 200, path
    caps = client.get("/api/v1/runtime/capabilities", headers=hdr)
    assert caps.json().get("mc_compatibility_version") == "phase4_step20"
