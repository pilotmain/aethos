from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.project import Project
from app.services.project_registry import get_default_project, get_project_by_key


def build_dev_job_payload_extras(
    db: Session, project: Project | None
) -> dict[str, Any]:
    if not project:
        return {
            "project_key": "aethos",
            "repo_path": None,
            "preferred_dev_tool": "aider",
            "dev_execution_mode": "autonomous_cli",
        }
    return {
        "project_key": project.key,
        "repo_path": project.repo_path,
        "preferred_dev_tool": project.preferred_dev_tool or "aider",
        "dev_execution_mode": project.dev_execution_mode or "autonomous_cli",
    }


def merge_dev_payload(
    base: dict[str, Any] | None, db: Session, project_key: str | None = None
) -> dict[str, Any]:
    """Merge static payload with resolved default or keyed project dev settings."""
    pk = (project_key or "").strip() or None
    p = get_project_by_key(db, pk) if pk else get_default_project(db)
    out = dict(base or {})
    out.update(build_dev_job_payload_extras(db, p))
    return out


def describe_dev_queue_line(project: Project | None) -> str:
    """User-facing one-liner for how the job will run (tool + mode)."""
    if not project:
        return "AethOS (autonomous / Aider when configured)"
    mode = (project.dev_execution_mode or "autonomous_cli").strip()
    tool = (project.preferred_dev_tool or "aider").strip()
    if mode == "ide_handoff":
        from app.services.dev_tools.registry import get_dev_tool

        t = get_dev_tool(tool)
        name = t.display_name if t else tool  # type: ignore[union-attr]
        return f"{project.display_name} using {name} handoff"
    if mode == "manual_review":
        return f"{project.display_name} (manual review — see task file)"
    if mode == "github_pr":
        return f"{project.display_name} (GitHub PR mode — not implemented yet in worker)"
    if tool == "aider":
        return f"{project.display_name} using Aider"
    from app.services.dev_tools.registry import get_dev_tool

    t2 = get_dev_tool(tool)
    tname = t2.display_name if t2 else tool  # type: ignore[union-attr]
    return f"{project.display_name} using {tname} (autonomous_cli)"
