# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 3 Step 8 — worker detail, deliverable export, follow-up priority."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.runtime.agent_work_state import link_registry_agent_to_runtime
from app.runtime.worker_operational_memory import (
    create_continuation,
    get_worker_memory_limits,
    persist_deliverable,
    set_session_active_worker,
)
from app.services.mission_control.worker_deliverable_ops import (
    build_deliverable_detail,
    build_worker_detail,
    export_deliverable,
    format_worker_result_reply,
    resolve_followup_priority,
)


def test_worker_detail_api(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    row = link_registry_agent_to_runtime(registry_agent_id="wd1", name="repairer", domain="ops")
    aid = str(row["agent_id"])
    persist_deliverable(
        worker_id=aid,
        task_id="t1",
        deliverable_type="repair_summary",
        summary="fixed build",
        content="patch applied",
        title="Repair report",
    )
    r = client.get(f"/api/v1/mission-control/runtime-workers/{aid}", headers={"X-User-Id": uid})
    assert r.status_code == 200
    body = r.json()
    assert body.get("found") is True
    assert body.get("handle")
    assert body.get("deliverables")


def test_worker_deliverables_subroute(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    row = link_registry_agent_to_runtime(registry_agent_id="wd2", name="analyst", domain="marketing")
    aid = str(row["agent_id"])
    did = persist_deliverable(
        worker_id=aid,
        task_id="t2",
        deliverable_type="research_summary",
        summary="market scan",
        content="data",
    )
    r = client.get(
        f"/api/v1/mission-control/runtime-workers/{aid}/deliverables",
        headers={"X-User-Id": uid},
    )
    assert r.status_code == 200
    assert any(d.get("deliverable_id") == did for d in r.json().get("deliverables", []))


def test_deliverable_detail_and_export() -> None:
    did = persist_deliverable(
        worker_id="wexp",
        task_id="t3",
        deliverable_type="general_output",
        summary="export me",
        content="body text",
        title="Export sample",
    )
    detail = build_deliverable_detail(did)
    assert detail.get("found") is True
    ex = export_deliverable(did, fmt="markdown")
    assert ex.get("ok") and "Export sample" in ex.get("body", "")
    exj = export_deliverable(did, fmt="json")
    assert exj.get("ok") and "deliverable_id" in exj.get("body", "")


def test_followup_priority_explicit_mention() -> None:
    row = link_registry_agent_to_runtime(registry_agent_id="fp1", name="finder", domain="research")
    aid = str(row["agent_id"])
    persist_deliverable(
        worker_id=aid,
        task_id="t4",
        deliverable_type="research_summary",
        summary="key insight",
        content="insight body",
    )
    reply, src = resolve_followup_priority("what did @finder produce?", chat_key="web:test")
    assert reply and src in ("what_did_agent", "explicit_mention")


def test_continuation_metadata_fields() -> None:
    cid = create_continuation(
        worker_id="w1",
        source_task_id="t9",
        source_deliverable_id="dlv_abc",
        continuation_prompt="continue research",
        status="queued",
    )
    from app.runtime.worker_operational_memory import list_continuations_for_worker

    rows = list_continuations_for_worker("w1", limit=5)
    match = [r for r in rows if r.get("continuation_id") == cid]
    assert match
    assert match[0].get("source_deliverable_id") == "dlv_abc"
    assert match[0].get("continuation_prompt") == "continue research"
    assert match[0].get("status") == "queued"


def test_memory_limits_from_settings() -> None:
    limits = get_worker_memory_limits()
    assert limits["task"] >= 4
    assert limits["deliverable"] >= 50


def test_format_worker_result_quality() -> None:
    row = link_registry_agent_to_runtime(registry_agent_id="rq1", name="writer", domain="content")
    aid = str(row["agent_id"])
    persist_deliverable(
        worker_id=aid,
        task_id="t5",
        deliverable_type="research_summary",
        summary="quality summary",
        content="details",
    )
    text = format_worker_result_reply(aid)
    assert "Summary" in text and "Deliverables" in text


def test_mc_deliverables_export_route(api_client: tuple[TestClient, str]) -> None:
    client, uid = api_client
    did = persist_deliverable(
        worker_id="wroute",
        task_id="t6",
        deliverable_type="deployment_report",
        summary="deployed",
        content="ok",
    )
    r = client.get(
        f"/api/v1/mission-control/deliverables/{did}/export?format=text",
        headers={"X-User-Id": uid},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_build_worker_detail_not_found() -> None:
    d = build_worker_detail("missing_worker_xyz")
    assert d.get("found") is False
