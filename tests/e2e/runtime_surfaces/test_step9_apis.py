# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_step9_mc_experience_apis(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    hdr = {"X-User-Id": uid}
    for path in (
        "/api/v1/mission-control/governance-experience",
        "/api/v1/mission-control/executive-overview",
        "/api/v1/mission-control/runtime-story",
        "/api/v1/mission-control/explainability",
        "/api/v1/mission-control/timeline-experience",
        "/api/v1/mission-control/workers/ecosystem",
    ):
        r = client.get(path, headers=hdr)
        assert r.status_code == 200, path
    caps = client.get("/api/v1/runtime/capabilities", headers=hdr)
    assert caps.json().get("mc_compatibility_version") == "phase4_step9"
