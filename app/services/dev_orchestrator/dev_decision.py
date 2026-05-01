from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.dev_orchestrator.project_intelligence import ProjectProfile
from app.services.dev_orchestrator.task_classifier import DevTaskProfile


@dataclass
class DevExecutionDecision:
    tool_key: str
    mode: str
    risk_level: str
    needs_approval: bool
    reason: str
    warnings: list[str]


def decide_dev_execution(
    project: Any,
    project_profile: ProjectProfile,
    task_profile: DevTaskProfile,
) -> DevExecutionDecision:
    warnings: list[str] = []

    configured_tool = (getattr(project, "preferred_dev_tool", None) or "").strip() or None
    configured_mode = (getattr(project, "dev_execution_mode", None) or "").strip() or None

    if not project_profile.exists:
        return DevExecutionDecision(
            tool_key="manual",
            mode="manual_review",
            risk_level="high",
            needs_approval=True,
            reason="Project repo path does not exist.",
            warnings=["Project needs a valid repo_path before code execution."],
        )

    if not project_profile.is_git_repo:
        return DevExecutionDecision(
            tool_key="manual",
            mode="manual_review",
            risk_level="high",
            needs_approval=True,
            reason="Project is not a git repository.",
            warnings=["Initialize git before autonomous code changes."],
        )

    if project_profile.dirty:
        return DevExecutionDecision(
            tool_key=configured_tool or "manual",
            mode="manual_review",
            risk_level="high",
            needs_approval=True,
            reason="Working tree is dirty.",
            warnings=[
                "Autonomous code changes are paused until the repo is clean.",
                "Commit, stash, or discard current changes first.",
            ],
        )

    tool_key = configured_tool or (
        project_profile.recommended_tools[0]
        if project_profile.recommended_tools
        else "aider"
    )
    mode = configured_mode or task_profile.preferred_mode

    if task_profile.preferred_mode == "ide_handoff" and task_profile.risk_level in {
        "medium",
        "high",
    }:
        mode = "ide_handoff"

    if mode == "autonomous_cli" and tool_key not in {"aider"}:
        warnings.append(
            f"{tool_key} does not support autonomous CLI execution; switching to ide_handoff."
        )
        mode = "ide_handoff"

    if mode == "ide_handoff" and tool_key == "aider":
        fallback = next(
            (
                t
                for t in project_profile.recommended_tools
                if t not in {"aider", "manual"}
            ),
            "manual",
        )
        tool_key = fallback

    return DevExecutionDecision(
        tool_key=tool_key,
        mode=mode,
        risk_level=task_profile.risk_level,
        needs_approval=True,
        reason=task_profile.reason,
        warnings=warnings,
    )
