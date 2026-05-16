# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from fastapi.testclient import TestClient


def test_phase4_runtime_evolution_api_smoke(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    headers = {"X-User-Id": uid}
    paths = (
        "/api/v1/mission-control/runtime/strategy",
        "/api/v1/mission-control/runtime/maturity",
        "/api/v1/mission-control/runtime/evolution",
        "/api/v1/mission-control/runtime/trends",
        "/api/v1/mission-control/workers/effectiveness",
        "/api/v1/mission-control/automation/effectiveness",
        "/api/v1/mission-control/governance/maturity",
        "/api/v1/mission-control/enterprise/overview",
    )
    for path in paths:
        r = client.get(path, headers=headers)
        assert r.status_code == 200, path
