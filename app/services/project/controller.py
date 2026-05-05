"""
Project / task controller — CRUD, checkout, mission tree (Phase 27).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import get_settings
from app.services.project.lock import lock_for_task
from app.services.project.mission_tree import build_mission_tree
from app.services.project.models import Project, ProjectStatus, Task, TaskStatus
from app.services.project.persistence import (
    MissionControlStateStore,
    ProjectStore,
    TaskStore,
)
from app.services.team.roster import TeamRoster

logger = logging.getLogger(__name__)


class ProjectController:
    """Mission Control facade over SQLite stores + TeamRoster."""

    def __init__(
        self,
        *,
        project_store: ProjectStore | None = None,
        task_store: TaskStore | None = None,
        state_store: MissionControlStateStore | None = None,
        team_roster: TeamRoster | None = None,
    ) -> None:
        self.project_store = project_store or ProjectStore()
        self.task_store = task_store or TaskStore()
        self.state_store = state_store or MissionControlStateStore()
        self._team_roster = team_roster

    @property
    def team_roster(self) -> TeamRoster:
        if self._team_roster is None:
            self._team_roster = TeamRoster()
        return self._team_roster

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _lock_timeout_seconds(self) -> int:
        return max(60, int(get_settings().nexa_task_lock_timeout_seconds))

    def _member_ok(self, member_id: str) -> bool:
        settings = get_settings()
        if not getattr(settings, "nexa_agent_orchestration_enabled", False):
            return bool(member_id.strip())
        return self.team_roster.get_member(member_id) is not None

    # --- projects ---

    def create_project(
        self,
        name: str,
        goal: str,
        team_scope: str,
        parent_id: str | None = None,
        *,
        organization_id: str | None = None,
        team_id: str | None = None,
    ) -> Project:
        project = Project.create(
            name=name,
            goal=goal,
            team_scope=team_scope,
            parent_id=parent_id,
            organization_id=organization_id,
            team_id=team_id,
        )
        self.project_store.save(project)
        self.state_store.set_current_project_id(team_scope, project.id)
        logger.info("Created MC project %s (%s)", project.id, project.name)
        return project

    def get_project(self, project_id: str) -> Project | None:
        return self.project_store.get(project_id)

    def list_projects(
        self,
        team_scope: str,
        status: ProjectStatus | None = None,
        *,
        organization_id: str | None = None,
    ) -> list[Project]:
        projects = self.project_store.list_by_scope(team_scope, organization_id=organization_id)
        if status is not None:
            projects = [p for p in projects if p.status == status]
        return sorted(projects, key=lambda p: p.created_at, reverse=True)

    def update_project_status(self, project_id: str, status: ProjectStatus) -> bool:
        project = self.project_store.get(project_id)
        if not project:
            return False
        project.status = status
        if status == ProjectStatus.COMPLETED:
            project.completed_at = self._now()
        project.updated_at = self._now()
        self.project_store.save(project)
        return True

    def set_current_project(self, team_scope: str, project_id: str | None) -> bool:
        if project_id is None:
            self.state_store.set_current_project_id(team_scope, None)
            return True
        p = self.project_store.get(project_id)
        if not p or p.team_scope != team_scope:
            return False
        self.state_store.set_current_project_id(team_scope, project_id)
        return True

    def get_current_project_id(self, team_scope: str) -> str | None:
        return self.state_store.get_current_project_id(team_scope)

    # --- tasks ---

    def add_task(
        self,
        title: str,
        *,
        project_id: str | None = None,
        team_scope: str | None = None,
        description: str | None = None,
    ) -> Task:
        org_id: str | None = None
        tm_id: str | None = None
        if project_id:
            proj = self.project_store.get(project_id)
            if proj:
                team_scope = proj.team_scope
                org_id = proj.organization_id
                tm_id = proj.team_id
        task = Task.create(
            title,
            project_id=project_id,
            team_scope=team_scope,
            description=description,
            organization_id=org_id,
            team_id=tm_id,
        )
        if project_id:
            existing = self.task_store.list_by_project(project_id)
        else:
            existing = [t for t in self.task_store.list_by_scope(team_scope or "") if t.project_id is None]
        task.order_index = len(existing)
        self.task_store.save(task)
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self.task_store.get(task_id)

    def list_tasks(
        self,
        *,
        project_id: str | None = None,
        team_scope: str | None = None,
        assigned_to: str | None = None,
    ) -> list[Task]:
        if project_id is not None:
            tasks = self.task_store.list_by_project(project_id)
        elif assigned_to is not None:
            tasks = self.task_store.list_by_assignee(assigned_to)
        elif team_scope is not None:
            tasks = self.task_store.list_by_scope(team_scope)
        else:
            tasks = self.task_store.list_all()
        return sorted(tasks, key=lambda t: (t.order_index, t.created_at))

    def assign_task(self, task_id: str, member_id: str, assigned_by: str) -> bool:
        if not self._member_ok(member_id):
            return False
        task = self.task_store.get(task_id)
        if not task:
            return False
        task.assign(member_id, assigned_by)
        task.updated_at = self._now()
        self.task_store.save(task)
        self.team_roster.set_member_task(member_id, task.title)
        return True

    def claim_task(self, task_id: str, member_id: str) -> bool:
        if not self._member_ok(member_id):
            return False
        self.task_store.clear_expired_locks(
            older_than_seconds=self._lock_timeout_seconds(),
            now=self._now(),
        )
        task = self.task_store.get(task_id)
        if not task or task.status == TaskStatus.DONE:
            return False
        with lock_for_task(task_id):
            if self.task_store.try_claim_atomic(task_id, member_id, self._now()):
                t2 = self.task_store.get(task_id)
                if t2:
                    self.team_roster.set_member_task(member_id, t2.title)
                return True
        return False

    def unclaim_task(self, task_id: str, member_id: str) -> bool:
        ok = self.task_store.try_release_lock_atomic(task_id, member_id, self._now())
        if ok:
            self.team_roster.set_member_task(member_id, None)
        return ok

    def complete_task(self, task_id: str, member_id: str) -> bool:
        task = self.task_store.get(task_id)
        if not task:
            return False
        if task.status == TaskStatus.DONE:
            return False
        allowed = False
        if task.assigned_to:
            allowed = task.assigned_to == member_id
        elif task.locked_by:
            allowed = task.locked_by == member_id
        else:
            allowed = bool(member_id.strip())
        if not allowed:
            return False
        task.complete()
        task.updated_at = self._now()
        self.task_store.save(task)
        self.team_roster.set_member_task(member_id, None)

        if task.project_id:
            pts = self.task_store.list_by_project(task.project_id)
            if pts and all(t.status == TaskStatus.DONE for t in pts):
                self.update_project_status(task.project_id, ProjectStatus.COMPLETED)
        return True

    def build_mission_tree(self, project_id: str) -> dict[str, Any]:
        return build_mission_tree(self.project_store, self.task_store, project_id)

    def get_dashboard(self, team_scope: str) -> dict[str, Any]:
        projects = self.list_projects(team_scope, status=ProjectStatus.ACTIVE)
        tasks = self.task_store.list_by_scope(team_scope)
        in_prog = [t for t in tasks if t.status == TaskStatus.IN_PROGRESS]
        return {
            "active_projects": len(projects),
            "total_tasks": len(tasks),
            "in_progress_tasks": len(in_prog),
            "projects": [p.to_user_display() for p in projects[:5]],
            "recent_tasks": [t.to_user_display() for t in tasks[:10]],
        }


__all__ = ["ProjectController"]
