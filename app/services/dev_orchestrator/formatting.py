from __future__ import annotations

from typing import Any

from app.services.dev_orchestrator.dev_decision import DevExecutionDecision
from app.services.dev_orchestrator.project_intelligence import ProjectProfile
from app.services.dev_orchestrator.task_classifier import DevTaskProfile


def format_dev_execution_plan(
    project: Any,
    project_profile: ProjectProfile,
    task_profile: DevTaskProfile,
    decision: DevExecutionDecision,
) -> str:
    warnings = ""
    if decision.warnings:
        warnings = "\n\nWarnings:\n" + "\n".join(f"— {w}" for w in decision.warnings)

    project_types = (
        ", ".join(project_profile.project_types) if project_profile.project_types else "unknown"
    )
    signals = ", ".join(project_profile.signals) if project_profile.signals else "none"
    dname = getattr(project, "display_name", None) or getattr(project, "key", None) or "Nexa"
    rpath = getattr(project, "repo_path", None) or project_profile.repo_path or "—"

    return (
        f"Development execution plan\n\n"
        f"Project: {dname}\n"
        f"Repo: {rpath}\n"
        f"Detected type: {project_types}\n"
        f"Signals: {signals}\n\n"
        f"Task:\n"
        f"— Type: {task_profile.task_type}\n"
        f"— Complexity: {task_profile.complexity}\n"
        f"— Risk: {task_profile.risk_level}\n\n"
        f"Execution:\n"
        f"— Tool: {decision.tool_key}\n"
        f"— Mode: {decision.mode}\n"
        f"— Reason: {decision.reason}\n"
        f"{warnings}"
    ).strip()
