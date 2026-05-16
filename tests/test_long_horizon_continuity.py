# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.worker_operational_memory import persist_deliverable, recover_worker_continuity
from app.runtime.workspace_operational_memory import get_research_chain, list_research_chains


def test_research_survives_continuation_recovery() -> None:
    did = persist_deliverable(
        worker_id="lh1",
        task_id="t1",
        deliverable_type="research_summary",
        summary="long horizon",
        content="body",
        project_id="p1",
    )
    chains = list_research_chains(project_id="p1", limit=5)
    assert chains
    assert did in (chains[0].get("related_deliverables") or [])
    n = recover_worker_continuity()
    assert n >= 0
    chain = get_research_chain(chains[0]["research_chain_id"])
    assert chain and did in (chain.get("related_deliverables") or [])
