# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from fastapi.testclient import TestClient

from app.runtime.worker_operational_memory import persist_deliverable, search_deliverables


def test_search_by_type() -> None:
    persist_deliverable(
        worker_id="w1",
        task_id="t1",
        deliverable_type="deployment_report",
        summary="deploy ok",
        content="done",
    )
    rows = search_deliverables(deliverable_type="deployment_report", limit=5)
    assert any(r.get("type") == "deployment_report" for r in rows)


def test_mc_deliverables_api(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    r = client.get("/api/v1/mission-control/worker-deliverables", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert "deliverables" in r.json()
