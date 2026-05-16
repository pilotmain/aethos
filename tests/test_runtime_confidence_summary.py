# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.mission_control.runtime_confidence import build_runtime_confidence
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_runtime_confidence_shape() -> None:
    truth = build_runtime_truth(user_id=None)
    conf = truth.get("runtime_confidence") or build_runtime_confidence(truth)
    rc = conf.get("runtime_confidence") or {}
    assert "health" in rc
    assert "uptime_hours" in rc
    assert "restart_count" in rc
    assert "provider_failures_24h" in rc


def test_mc_runtime_confidence_api(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/runtime-confidence", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "runtime_confidence" in r.json()
