# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient

from app.services.enterprise_runtime_visibility import build_enterprise_runtime_panels


def test_enterprise_panels_keys() -> None:
    p = build_enterprise_runtime_panels({})
    for key in (
        "runtime_reliability",
        "automation_health",
        "governance_health",
        "operational_risk",
        "provider_stability",
        "deployment_reliability",
        "worker_reliability",
        "workspace_health",
    ):
        assert key in p


def test_mc_enterprise_runtime(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/enterprise-runtime", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "automation_health" in r.json()
