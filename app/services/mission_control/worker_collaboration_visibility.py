# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Worker collaboration chains for Mission Control (Phase 3 Step 9)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_agents import list_runtime_agents
from app.runtime.worker_operational_memory import list_deliverables_for_worker, list_continuations_for_worker
from app.runtime.workspace_operational_memory import relationships_for_deliverable


def build_worker_collaboration_chains(*, limit: int = 8) -> list[dict[str, Any]]:
    chains: list[dict[str, Any]] = []
    agents = list_runtime_agents(include_expired=True)
    for aid, row in list(agents.items())[:limit]:
        if not isinstance(row, dict) or row.get("system"):
            continue
        dels = list_deliverables_for_worker(str(aid), limit=4)
        conts = list_continuations_for_worker(str(aid), limit=3)
        rels: list[dict[str, Any]] = []
        for d in dels[:2]:
            rels.extend(relationships_for_deliverable(str(d.get("deliverable_id") or "")))
        chains.append(
            {
                "orchestrator": "aethos",
                "worker_id": aid,
                "handle": row.get("handle"),
                "role": row.get("role"),
                "deliverables": [d.get("deliverable_id") for d in dels],
                "continuations": [c.get("continuation_id") for c in conts],
                "relationships": rels[:6],
                "chain": ["orchestrator", "runtime_worker", "task", "deliverable"],
            }
        )
    return chains
