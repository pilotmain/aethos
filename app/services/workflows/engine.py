# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Topological workflow execution with bounded steps."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Callable

from app.services.workflows.schema import WorkflowDefinition, WorkflowStep

StepHandler = Callable[[WorkflowStep], dict[str, Any]]

MAX_STEPS = 64


def _toposort(steps: list[WorkflowStep]) -> list[WorkflowStep]:
    ids = {s.id for s in steps}
    for s in steps:
        for d in s.depends_on:
            if d not in ids:
                raise ValueError(f"unknown dependency {d!r} for step {s.id}")
    indeg: dict[str, int] = defaultdict(int)
    adj: dict[str, list[str]] = defaultdict(list)
    for s in steps:
        indeg[s.id] = 0
    for s in steps:
        for d in s.depends_on:
            adj[d].append(s.id)
            indeg[s.id] += 1
    q = deque([sid for sid, deg in indeg.items() if deg == 0])
    out: list[WorkflowStep] = []
    idmap = {s.id: s for s in steps}
    while q:
        if len(out) >= MAX_STEPS:
            raise ValueError("workflow exceeds max steps")
        n = q.popleft()
        out.append(idmap[n])
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    if len(out) != len(steps):
        raise ValueError("cycle or unresolved dependencies in workflow")
    return out


def run_workflow(
    wf: WorkflowDefinition,
    handlers: dict[str, StepHandler],
    *,
    max_steps: int = MAX_STEPS,
) -> dict[str, Any]:
    """
    Executes steps in dependency order. Stops on first handler error (``ok`` False).
    """
    if len(wf.steps) > max_steps:
        raise ValueError("too many steps")
    order = _toposort(wf.steps)
    results: dict[str, dict[str, Any]] = {}
    for step in order:
        fn = handlers.get(step.type)
        if fn is None:
            return {"ok": False, "failed_step": step.id, "error": f"no handler for {step.type}"}
        try:
            r = fn(step)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "failed_step": step.id, "error": str(e)}
        results[step.id] = r
        if not r.get("ok", True):
            return {"ok": False, "failed_step": step.id, "partial": results}
    return {"ok": True, "results": results}


__all__ = ["run_workflow"]
