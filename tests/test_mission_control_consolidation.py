# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient

from app.services.mission_control.mission_control_cohesion import build_cohesion_report
from app.services.mission_control.runtime_truth import build_runtime_panels_from_truth, build_runtime_truth


def test_cohesion_report_complete() -> None:
    truth = build_runtime_truth()
    report = build_cohesion_report(truth)
    assert report.get("single_truth_path") is True
    assert report.get("cohesive") is True


def test_panels_from_truth() -> None:
    truth = build_runtime_truth()
    panels = build_runtime_panels_from_truth(truth)
    assert "enterprise_operational_health" in panels


def test_mc_operational_summary_api(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/operational-summary", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert r.json().get("single_truth_path") is True
