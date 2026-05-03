from __future__ import annotations

import pytest

from app.services.workflows.engine import run_workflow
from app.services.workflows.schema import WorkflowDefinition, WorkflowStep
from app.services.workflows.yaml_loader import load_workflow_yaml


def test_topo_and_yaml() -> None:
    txt = """
name: fix-tests
steps:
  - id: inspect
    type: dev.inspect
  - id: test
    type: dev.test
    depends_on: [inspect]
"""
    wf = load_workflow_yaml(txt)
    assert wf.name == "fix-tests"

    def h(step: WorkflowStep):
        return {"ok": True, "id": step.id}

    out = run_workflow(wf, {"dev.inspect": h, "dev.test": h})
    assert out["ok"] is True


def test_cycle_detected() -> None:
    wf = WorkflowDefinition(
        name="bad",
        steps=[
            WorkflowStep(id="a", type="t", depends_on=["b"]),
            WorkflowStep(id="b", type="t", depends_on=["a"]),
        ],
    )

    def h(step: WorkflowStep):
        return {"ok": True}

    with pytest.raises(ValueError):
        run_workflow(wf, {"t": h})
