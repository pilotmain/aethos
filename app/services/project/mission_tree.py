"""
Mission tree / goal ancestry helpers (Phase 27).

Builds structured summaries for dashboards and `/mission` output.
"""

from __future__ import annotations

from typing import Any

from app.services.project.models import Task, TaskStatus
from app.services.project.persistence import ProjectStore, TaskStore


def _task_item(t: Task) -> dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status.value,
        "assigned_to": t.assigned_to,
        "updated_at": t.updated_at.isoformat(),
        "order_index": t.order_index,
    }


def build_mission_tree(
    project_store: ProjectStore,
    task_store: TaskStore,
    project_id: str,
    *,
    recurse: bool = True,
) -> dict[str, Any]:
    project = project_store.get(project_id)
    if not project:
        return {"error": "Project not found"}

    tasks = task_store.list_by_project(project_id)
    pending = [t for t in tasks if t.status == TaskStatus.PENDING]
    in_progress = [t for t in tasks if t.status == TaskStatus.IN_PROGRESS]
    done = [t for t in tasks if t.status == TaskStatus.DONE]
    blocked = [t for t in tasks if t.status == TaskStatus.BLOCKED]

    total = len(tasks)
    completed_count = len(done)
    progress = int((completed_count / total) * 100) if total > 0 else 0

    child_projects = project_store.list_by_parent(project_id)
    sub_trees: list[dict[str, Any]] = []
    if recurse:
        for cp in child_projects:
            sub_trees.append(
                build_mission_tree(project_store, task_store, cp.id, recurse=True),
            )

    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "goal": project.goal,
            "status": project.status.value,
            "progress": progress,
            "created_at": project.created_at.isoformat(),
            "completed_at": project.completed_at.isoformat() if project.completed_at else None,
        },
        "tasks": {
            "total": total,
            "pending": len(pending),
            "in_progress": len(in_progress),
            "done": completed_count,
            "blocked": len(blocked),
            "list": [t.to_user_display() for t in tasks],
            "items": [_task_item(t) for t in tasks],
        },
        "sub_projects": sub_trees,
        "why_this_matters": project.goal,
    }


__all__ = ["build_mission_tree"]
