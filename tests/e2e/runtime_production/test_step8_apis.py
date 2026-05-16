# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_step8_runtime_apis(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    hdr = {"X-User-Id": uid}
    for path in (
        "/api/v1/runtime/summaries",
        "/api/v1/runtime/partitions",
        "/api/v1/runtime/eras",
        "/api/v1/runtime/production-posture",
        "/api/v1/runtime/calmness-lock",
        "/api/v1/mission-control/governance/index",
        "/api/v1/mission-control/workers/lifecycle",
    ):
        r = client.get(path, headers=hdr)
        assert r.status_code == 200, path
    caps = client.get("/api/v1/runtime/capabilities", headers=hdr)
    assert caps.json().get("mc_compatibility_version") == "phase4_step8"
