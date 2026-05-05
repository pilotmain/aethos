"""
Project and Task models for Mission Control (Phase 27). User-friendly names, stable enums.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


@dataclass
class Project:
    """A project = a mission with a goal (user: /goal \"Build e-commerce site\")."""

    id: str
    name: str
    goal: str
    status: ProjectStatus = ProjectStatus.ACTIVE
    parent_project_id: str | None = None
    team_scope: str | None = None
    organization_id: str | None = None
    team_id: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        name: str,
        goal: str,
        team_scope: str,
        *,
        parent_id: str | None = None,
        organization_id: str | None = None,
        team_id: str | None = None,
    ) -> Project:
        return cls(
            id=str(uuid.uuid4())[:8],
            name=name.strip(),
            goal=goal.strip(),
            team_scope=team_scope,
            parent_project_id=parent_id,
            organization_id=organization_id,
            team_id=team_id,
        )

    def to_user_display(self) -> str:
        emoji = {
            ProjectStatus.ACTIVE: "🟢",
            ProjectStatus.PAUSED: "⏸️",
            ProjectStatus.COMPLETED: "✅",
            ProjectStatus.ARCHIVED: "📦",
        }.get(self.status, "⚪")
        return f"{emoji} {self.name}\n   📍 Goal: {self.goal}"


@dataclass
class Task:
    """A unit of work; may belong to a project and a team member (sub-agent id)."""

    id: str
    title: str
    description: str | None = None
    project_id: str | None = None
    team_scope: str | None = None
    organization_id: str | None = None
    team_id: str | None = None
    assigned_to: str | None = None
    assigned_by: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    locked_by: str | None = None
    locked_at: datetime | None = None
    parent_task_id: str | None = None
    goal_link: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    completed_at: datetime | None = None
    order_index: int = 0

    @classmethod
    def create(
        cls,
        title: str,
        *,
        project_id: str | None = None,
        team_scope: str | None = None,
        description: str | None = None,
        organization_id: str | None = None,
        team_id: str | None = None,
    ) -> Task:
        return cls(
            id=str(uuid.uuid4())[:8],
            title=title.strip(),
            description=(description or "").strip() or None,
            project_id=project_id,
            team_scope=team_scope,
            organization_id=organization_id,
            team_id=team_id,
        )

    def assign(self, member_id: str, assigned_by: str) -> None:
        self.assigned_to = member_id
        self.assigned_by = assigned_by
        if self.status == TaskStatus.PENDING:
            pass

    def complete(self) -> None:
        self.status = TaskStatus.DONE
        self.completed_at = _utcnow()
        self.locked_by = None
        self.locked_at = None

    def to_user_display(self, *, show_project: bool = False) -> str:
        emoji = {
            TaskStatus.PENDING: "⏳",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.DONE: "✅",
            TaskStatus.BLOCKED: "🚫",
        }.get(self.status, "⚪")
        assign = f" (→ {self.assigned_to})" if self.assigned_to else ""
        lines = [f"{emoji} {self.title}{assign}"]
        if self.description:
            lines.append(f"   📝 {self.description}")
        if self.goal_link and not show_project:
            lines.append(f"   🎯 {self.goal_link}")
        return "\n".join(lines)


__all__ = [
    "Project",
    "ProjectStatus",
    "Task",
    "TaskStatus",
]
