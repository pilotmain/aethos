# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from fastapi.testclient import TestClient

from app.runtime.worker_operational_memory import persist_deliverable
from app.services.research_continuity import ensure_research_deliverable_linked


def test_e2e_research_chain_api(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    did = persist_deliverable(
        worker_id="e2e_r",
        task_id="t1",
        deliverable_type="research_summary",
        summary="e2e chain",
        content="data",
    )
    cid = ensure_research_deliverable_linked(deliverable_id=did, topic="e2e")
    r = client.get(f"/api/v1/mission-control/research-chains/{cid}", headers={"X-User-Id": uid})
    assert r.status_code == 200
    assert r.json().get("found") is True
