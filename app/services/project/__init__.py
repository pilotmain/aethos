"""
Phase 27 — Mission Control **projects** and **tasks** (goal tree, checkout).

Telegram: ``/goal``, ``/task``, ``/tasks``, ``/assign``, ``/claim``, ``/unclaim``, ``/done``, ``/mission``, ``/mcstatus``
(``/project`` is reserved for workspace projects — see docs/PROJECT_MANAGEMENT.md).
"""

from __future__ import annotations

from app.services.project.controller import ProjectController
from app.services.project.models import Project, ProjectStatus, Task, TaskStatus

_project_controller: ProjectController | None = None


def get_project_controller() -> ProjectController:
    global _project_controller
    if _project_controller is None:
        _project_controller = ProjectController()
    return _project_controller


__all__ = [
    "Project",
    "ProjectController",
    "ProjectStatus",
    "Task",
    "TaskStatus",
    "get_project_controller",
]
