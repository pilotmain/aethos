# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.worker_operational_memory import persist_deliverable, search_deliverables


def test_filter_status_and_project() -> None:
    persist_deliverable(
        worker_id="wf1",
        task_id="t1",
        deliverable_type="repair_summary",
        summary="failed repair",
        content="err",
        project_id="invoicepilot",
        status="failed",
    )
    persist_deliverable(
        worker_id="wf1",
        task_id="t2",
        deliverable_type="repair_summary",
        summary="ok repair",
        content="ok",
        project_id="invoicepilot",
        status="final",
    )
    failed = search_deliverables(project_id="invoicepilot", status="failed", limit=10)
    assert any(r.get("status") == "failed" for r in failed)
    assert not any(r.get("summary") == "ok repair" for r in failed)


def test_filter_task_id() -> None:
    persist_deliverable(
        worker_id="wf2",
        task_id="task_unique_99",
        deliverable_type="research_summary",
        summary="scoped",
        content="x",
    )
    rows = search_deliverables(task_id="task_unique_99", limit=5)
    assert rows and all(r.get("task_id") == "task_unique_99" for r in rows)
