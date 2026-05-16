# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient

from app.services.workspace_runtime_intelligence import build_operational_risk, build_workspace_intelligence


def test_workspace_intelligence_expanded_shape() -> None:
    out = build_workspace_intelligence()
    assert "projects" in out
    assert "risk_signals" in out
    assert "research_continuity" in out
    assert "summaries" in out


def test_operational_risk_shape() -> None:
    risk = build_operational_risk()
    assert "risk_signals" in risk
    assert "workspace_confidence" in risk


def test_mc_workspace_intelligence_api(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/workspace-intelligence", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "projects" in r.json()
