# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.worker_operational_memory import persist_deliverable
from app.services.research_continuity import (
    build_research_chain_view,
    compare_deliverables,
    ensure_research_deliverable_linked,
    resolve_research_followup,
)


def test_research_chain_linking() -> None:
    d1 = persist_deliverable(
        worker_id="rw1",
        task_id="t1",
        deliverable_type="research_summary",
        summary="first findings",
        content="a",
    )
    cid = ensure_research_deliverable_linked(
        deliverable_id=d1,
        project_id="proj1",
        worker_id="rw1",
        topic="market research",
    )
    assert cid
    view = build_research_chain_view(cid)
    assert view.get("found") is True
    assert d1 in (view.get("chain") or {}).get("related_deliverables", [])


def test_compare_deliverables() -> None:
    a = persist_deliverable(
        worker_id="rw2",
        task_id="t2",
        deliverable_type="research_summary",
        summary="alpha",
        content="x",
    )
    b = persist_deliverable(
        worker_id="rw2",
        task_id="t3",
        deliverable_type="research_summary",
        summary="beta",
        content="y",
    )
    out = compare_deliverables(a, b)
    assert out.get("ok") is True


def test_research_followup_continue() -> None:
    from app.runtime.agent_work_state import link_registry_agent_to_runtime
    from app.runtime.worker_operational_memory import set_session_active_worker

    row = link_registry_agent_to_runtime(registry_agent_id="rc1", name="researcher", domain="marketing")
    aid = str(row["agent_id"])
    persist_deliverable(
        worker_id=aid,
        task_id="t4",
        deliverable_type="research_summary",
        summary="competitor map",
        content="details",
    )
    set_session_active_worker("web:rc", aid)
    reply = resolve_research_followup("continue market research", chat_key="web:rc", worker_id=aid)
    assert reply and "Continuing" in reply
