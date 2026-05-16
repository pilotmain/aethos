# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Unified execution visibility chains (Phase 3 Step 14)."""

from __future__ import annotations

from typing import Any

from app.runtime.runtime_agents import ORCHESTRATOR_ID
from app.services.mission_control.runtime_ownership import build_all_operator_traces, build_operator_trace_chains


def build_execution_chains(truth: dict[str, Any] | None = None, *, user_id: str | None = None) -> list[dict[str, Any]]:
    """Operator → orchestrator → worker → continuation → provider → deliverable."""
    truth = truth or {}
    chains: list[dict[str, Any]] = []
    uid = user_id

    for trace in build_operator_trace_chains(uid)[:20]:
        steps = [
            {"role": "operator", "id": "operator"},
            {"role": "orchestrator", "id": ORCHESTRATOR_ID},
            {"role": "worker", "id": trace.get("runtime_agent_id")},
            {"role": "provider", "id": trace.get("provider"), "model": trace.get("model")},
        ]
        if trace.get("repair_context_id"):
            steps.insert(3, {"role": "repair", "id": trace.get("repair_context_id")})
        chains.append(
            {
                "chain_id": trace.get("task_id"),
                "task_id": trace.get("task_id"),
                "workflow_id": trace.get("workflow_id"),
                "steps": steps,
                "trace": trace.get("trace") or [],
                "state": trace.get("state"),
                "explainable": True,
            }
        )

    for d in (truth.get("worker_deliverables") or [])[:12]:
        if not isinstance(d, dict):
            continue
        chains.append(
            {
                "chain_id": f"dlv:{d.get('deliverable_id')}",
                "task_id": d.get("task_id"),
                "steps": [
                    {"role": "operator", "id": "operator"},
                    {"role": "orchestrator", "id": ORCHESTRATOR_ID},
                    {"role": "worker", "id": d.get("worker_id")},
                    {"role": "deliverable", "id": d.get("deliverable_id"), "type": d.get("type")},
                ],
                "outcome": d.get("status"),
                "summary": d.get("summary"),
            }
        )

    for c in (truth.get("worker_continuations") or [])[:8]:
        if not isinstance(c, dict):
            continue
        chains.append(
            {
                "chain_id": f"cont:{c.get('continuation_id') or c.get('worker_id')}",
                "steps": [
                    {"role": "worker", "id": c.get("worker_id")},
                    {"role": "continuation", "id": c.get("continuation_id")},
                ],
                "reason": c.get("reason") or c.get("continuation_prompt"),
            }
        )

    return chains[:32]


def build_execution_governance(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    gov = (truth or {}).get("runtime_governance") or {}
    summary = gov.get("summary") if isinstance(gov, dict) else {}
    return {
        "governance_visible": True,
        "plugin_actions": summary.get("plugin_actions") if isinstance(summary, dict) else 0,
        "provider_actions": summary.get("provider_actions") if isinstance(summary, dict) else 0,
        "privacy_events": summary.get("privacy_events") if isinstance(summary, dict) else 0,
        "requires_approval": True,
        "advisory_only": True,
    }


def build_execution_trace_health(truth: dict[str, Any] | None = None) -> dict[str, Any]:
    traces = build_all_operator_traces(None)
    n_own = len(traces.get("ownership") or [])
    n_prov = len(traces.get("provider") or [])
    n_rep = len(traces.get("repair") or [])
    total = n_own + n_prov + n_rep
    return {
        "trace_count": total,
        "ownership_traces": n_own,
        "provider_traces": n_prov,
        "repair_traces": n_rep,
        "complete": total > 0,
        "bounded": total <= 32,
    }


def build_execution_visibility(truth: dict[str, Any] | None = None, *, user_id: str | None = None) -> dict[str, Any]:
    chains = build_execution_chains(truth, user_id=user_id)
    return {
        "chains": chains,
        "chain_count": len(chains),
        "governance": build_execution_governance(truth),
        "trace_health": build_execution_trace_health(truth),
        "searchable": True,
        "privacy_aware": True,
        "operator_readable": True,
    }
