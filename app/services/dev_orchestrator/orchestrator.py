from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.services.dev_orchestrator.dev_decision import decide_dev_execution
from app.services.dev_orchestrator.formatting import format_dev_execution_plan
from app.services.dev_orchestrator.project_intelligence import detect_project_profile
from app.services.dev_orchestrator.task_classifier import classify_dev_task


def build_dev_execution_plan(project: Any, task_text: str) -> dict[str, Any]:
    project_profile = detect_project_profile(project)
    task_profile = classify_dev_task(task_text)
    decision = decide_dev_execution(project, project_profile, task_profile)
    message = format_dev_execution_plan(project, project_profile, task_profile, decision)

    return {
        "project_profile": project_profile,
        "task_profile": task_profile,
        "decision": decision,
        "message": message,
        "payload_fragment": {
            "task_text": (task_text or "").strip(),
            "project_profile": asdict(project_profile),
            "task_profile": asdict(task_profile),
            "execution_decision": {
                "tool_key": decision.tool_key,
                "mode": decision.mode,
                "risk_level": decision.risk_level,
                "needs_approval": decision.needs_approval,
                "reason": decision.reason,
                "warnings": list(decision.warnings),
            },
            "orchestrator": True,
            "orchestrator_version": 1,
        },
    }
