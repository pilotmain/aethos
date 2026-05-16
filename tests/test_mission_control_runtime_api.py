# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from fastapi.testclient import TestClient


def test_mc_runtime_endpoint(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/runtime", headers={"X-User-Id": uid})
    assert r.status_code == 200
    data = r.json()
    assert "runtime_health" in data
    assert "runtime_agents" in data
    assert "office" in data
    assert "aethos_orchestrator" in data["runtime_agents"]


def test_mc_runtime_agents_slice(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/agents", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "runtime_agents" in r.json()


def test_mc_runtime_metrics(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/runtime-metrics", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "metrics" in r.json()
