# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient

from app.runtime.worker_operational_memory import persist_deliverable


def test_e2e_deliverable_export(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    did = persist_deliverable(
        worker_id="e2e_w",
        task_id="e2e_t",
        deliverable_type="research_summary",
        summary="e2e export",
        content="full body",
    )
    r = client.get(
        f"/api/v1/mission-control/deliverables/{did}",
        headers={"X-User-Id": uid},
    )
    assert r.status_code == 200
    assert r.json().get("found") is True
