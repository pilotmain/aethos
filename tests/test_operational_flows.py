# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.worker_operational_memory import persist_deliverable, search_deliverables


def test_operational_flow_deliverable_types() -> None:
    for dtype, summary in (
        ("research_summary", "market scan"),
        ("deployment_report", "deploy diag"),
        ("repair_summary", "repair inv"),
    ):
        persist_deliverable(
            worker_id="flow1",
            task_id=f"t_{dtype}",
            deliverable_type=dtype,
            summary=summary,
            content="x",
        )
    assert search_deliverables(deliverable_type="research_summary", limit=5)
    assert search_deliverables(deliverable_type="deployment_report", limit=5)
    assert search_deliverables(deliverable_type="repair_summary", limit=5)
