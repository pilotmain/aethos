"""Load workflow definitions from YAML."""

from __future__ import annotations

from typing import Any

import yaml

from app.services.workflows.schema import WorkflowDefinition, WorkflowStep


def load_workflow_dict(raw: dict[str, Any]) -> WorkflowDefinition:
    name = str(raw.get("name") or "workflow")
    steps_in = raw.get("steps") or []
    if not isinstance(steps_in, list):
        raise ValueError("steps must be a list")
    steps: list[WorkflowStep] = []
    for s in steps_in:
        if not isinstance(s, dict):
            raise ValueError("each step must be a mapping")
        sid = str(s.get("id") or "").strip()
        st = str(s.get("type") or "").strip()
        if not sid or not st:
            raise ValueError("step requires id and type")
        dep = s.get("depends_on") or []
        if isinstance(dep, str):
            dep = [dep]
        if not isinstance(dep, list):
            raise ValueError("depends_on must be a list")
        steps.append(
            WorkflowStep(
                id=sid,
                type=st,
                depends_on=[str(x) for x in dep],
                meta={k: v for k, v in s.items() if k not in ("id", "type", "depends_on")},
            )
        )
    return WorkflowDefinition(name=name, steps=steps)


def load_workflow_yaml(text: str) -> WorkflowDefinition:
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValueError("root must be a mapping")
    return load_workflow_dict(raw)


__all__ = ["load_workflow_dict", "load_workflow_yaml"]
