# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from fastapi.testclient import TestClient


def test_mission_control_endpoints_no_500(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    hdr = {"X-User-Id": uid}
    for path in (
        "/api/v1/health",
        "/api/v1/setup/status",
        "/api/v1/setup/ready-state",
        "/api/v1/runtime/capabilities",
        "/api/v1/runtime/startup",
        "/api/v1/runtime/readiness",
        "/api/v1/runtime/bootstrap",
        "/api/v1/mission-control/onboarding",
        "/api/v1/mission-control/office",
    ):
        r = client.get(path, headers=hdr if path != "/api/v1/health" else {})
        assert r.status_code < 500, f"{path} -> {r.status_code}"
