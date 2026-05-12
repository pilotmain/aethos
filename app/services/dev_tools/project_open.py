# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.services.dev_tools.registry import get_dev_tool
from app.services.project_registry import get_default_project, get_project_by_key


def open_project_with_tool(
    db: Session, project_key: str | None = None
) -> str:
    pk = (project_key or "").strip() or None
    if pk:
        project = get_project_by_key(db, pk)
        if not project:
            return f"I don’t know project `{pk}`."
    else:
        project = get_default_project(db)

    if not project:
        return "No project configured."

    if not project.repo_path:
        return f"{project.display_name} does not have a repo path configured."

    repo_path = Path(project.repo_path)

    if not repo_path.exists():
        return f"Repo path does not exist: {repo_path}"

    tool_key = project.preferred_dev_tool or "manual"
    tool = get_dev_tool(str(tool_key))

    if not tool:
        return f"Unknown dev tool `{tool_key}`."

    result = tool.open_project(repo_path)  # type: ignore[union-attr]
    return result.message + (f"\n\n{result.details}" if result.details else "")
