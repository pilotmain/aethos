# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
SQLite persistence for Mission Control projects and tasks (Phase 27).

Uses a dedicated file under :attr:`Settings.nexa_data_dir` (``mission_control.db``)
so it does not share the main app ORM database.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.project.models import Project, ProjectStatus, Task, TaskStatus


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


class MissionControlStoreBase:
    """Shared DB path + schema init."""

    def __init__(self, db_path: Path | None = None) -> None:
        settings = get_settings()
        base = Path(getattr(settings, "nexa_data_dir", None) or "data")
        if not base.is_absolute():
            base = Path(__file__).resolve().parents[3] / base
        base.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path if db_path is not None else base / "mission_control.db"
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    parent_project_id TEXT,
                    team_scope TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    metadata TEXT
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    project_id TEXT,
                    team_scope TEXT,
                    assigned_to TEXT,
                    assigned_by TEXT,
                    status TEXT NOT NULL,
                    locked_by TEXT,
                    locked_at TEXT,
                    parent_task_id TEXT,
                    goal_link TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    order_index INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS mission_control_state (
                    team_scope TEXT PRIMARY KEY,
                    current_project_id TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mobile_push_tokens (
                    user_id TEXT PRIMARY KEY,
                    push_token TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            self._apply_rbac_migrations(conn)

    def _apply_rbac_migrations(self, conn: sqlite3.Connection) -> None:
        """Phase 29 — nullable organization_id / team_id on projects and tasks."""

        def _has(table: str, col: str) -> bool:
            cur = conn.execute(f"PRAGMA table_info({table})")
            return any(str(r[1]) == col for r in cur.fetchall())

        if not _has("projects", "organization_id"):
            conn.execute("ALTER TABLE projects ADD COLUMN organization_id TEXT")
        if not _has("projects", "team_id"):
            conn.execute("ALTER TABLE projects ADD COLUMN team_id TEXT")
        if not _has("tasks", "organization_id"):
            conn.execute("ALTER TABLE tasks ADD COLUMN organization_id TEXT")
        if not _has("tasks", "team_id"):
            conn.execute("ALTER TABLE tasks ADD COLUMN team_id TEXT")


class ProjectStore(MissionControlStoreBase):
    def save(self, project: Project) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO projects
                (id, name, goal, status, parent_project_id, team_scope,
                 created_at, updated_at, completed_at, metadata,
                 organization_id, team_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.id,
                    project.name,
                    project.goal,
                    project.status.value,
                    project.parent_project_id,
                    project.team_scope,
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                    project.completed_at.isoformat() if project.completed_at else None,
                    json.dumps(project.metadata or {}),
                    project.organization_id,
                    project.team_id,
                ),
            )

    def get(self, project_id: str) -> Project | None:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cur.fetchone()
        return self._row_to_project(row) if row else None

    def list_by_scope(
        self, team_scope: str, organization_id: str | None = None
    ) -> list[Project]:
        with self._connect() as conn:
            if organization_id:
                cur = conn.execute(
                    """
                    SELECT * FROM projects WHERE team_scope = ?
                      AND (organization_id IS NULL OR organization_id = ?)
                    ORDER BY created_at DESC
                    """,
                    (team_scope, organization_id),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM projects WHERE team_scope = ? ORDER BY created_at DESC",
                    (team_scope,),
                )
            return [self._row_to_project(r) for r in cur.fetchall()]

    def list_by_parent(self, parent_id: str) -> list[Project]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM projects WHERE parent_project_id = ? ORDER BY created_at ASC",
                (parent_id,),
            )
            return [self._row_to_project(r) for r in cur.fetchall()]

    def _row_to_project(self, row: sqlite3.Row) -> Project:
        keys = row.keys()
        return Project(
            id=str(row["id"]),
            name=str(row["name"]),
            goal=str(row["goal"]),
            status=ProjectStatus(str(row["status"])),
            parent_project_id=row["parent_project_id"],
            team_scope=row["team_scope"],
            organization_id=row["organization_id"] if "organization_id" in keys else None,
            team_id=row["team_id"] if "team_id" in keys else None,
            created_at=_parse_dt(row["created_at"]) or datetime.now(timezone.utc),
            updated_at=_parse_dt(row["updated_at"]) or datetime.now(timezone.utc),
            completed_at=_parse_dt(row["completed_at"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )


class TaskStore(MissionControlStoreBase):
    def save(self, task: Task) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks
                (id, title, description, project_id, team_scope, organization_id, team_id,
                 assigned_to, assigned_by,
                 status, locked_by, locked_at, parent_task_id, goal_link,
                 created_at, updated_at, completed_at, order_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.title,
                    task.description,
                    task.project_id,
                    task.team_scope,
                    task.organization_id,
                    task.team_id,
                    task.assigned_to,
                    task.assigned_by,
                    task.status.value,
                    task.locked_by,
                    task.locked_at.isoformat() if task.locked_at else None,
                    task.parent_task_id,
                    task.goal_link,
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.order_index,
                ),
            )

    def get(self, task_id: str) -> Task | None:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cur.fetchone()
        return self._row_to_task(row) if row else None

    def list_by_project(self, project_id: str) -> list[Task]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM tasks WHERE project_id = ?
                ORDER BY order_index ASC, created_at ASC
                """,
                (project_id,),
            )
            return [self._row_to_task(r) for r in cur.fetchall()]

    def list_by_assignee(self, assigned_to: str) -> list[Task]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT * FROM tasks WHERE assigned_to = ?
                ORDER BY created_at DESC
                """,
                (assigned_to,),
            )
            return [self._row_to_task(r) for r in cur.fetchall()]

    def list_by_scope(self, team_scope: str) -> list[Task]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT t.* FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE p.team_scope = ? OR (t.project_id IS NULL AND t.team_scope = ?)
                ORDER BY t.created_at DESC
                """,
                (team_scope, team_scope),
            )
            return [self._row_to_task(r) for r in cur.fetchall()]

    def list_all(self) -> list[Task]:
        with self._connect() as conn:
            cur = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC")
            return [self._row_to_task(r) for r in cur.fetchall()]

    def try_claim_atomic(self, task_id: str, member_id: str, now: datetime) -> bool:
        """Set lock + in_progress if currently unlocked and not done."""
        now_iso = now.isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE tasks SET
                    locked_by = ?,
                    locked_at = ?,
                    status = ?,
                    updated_at = ?
                WHERE id = ?
                  AND (locked_by IS NULL OR locked_by = '')
                  AND status != ?
                """,
                (
                    member_id,
                    now_iso,
                    TaskStatus.IN_PROGRESS.value,
                    now_iso,
                    task_id,
                    TaskStatus.DONE.value,
                ),
            )
            return cur.rowcount == 1

    def try_release_lock_atomic(self, task_id: str, member_id: str, now: datetime) -> bool:
        now_iso = now.isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE tasks SET
                    locked_by = NULL,
                    locked_at = NULL,
                    status = ?,
                    updated_at = ?
                WHERE id = ? AND locked_by = ?
                """,
                (TaskStatus.PENDING.value, now_iso, task_id, member_id),
            )
            return cur.rowcount == 1

    def clear_expired_locks(self, *, older_than_seconds: int, now: datetime) -> int:
        """Release stale locks (checkout timeout)."""
        cutoff = datetime.fromtimestamp(now.timestamp() - older_than_seconds, tz=timezone.utc)
        cutoff_iso = cutoff.isoformat()
        cleared = 0
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT id, locked_by FROM tasks
                WHERE locked_at IS NOT NULL AND locked_at < ?
                """,
                (cutoff_iso,),
            )
            rows = cur.fetchall()
            for r in rows:
                tid = str(r["id"])
                mid = str(r["locked_by"]) if r["locked_by"] else ""
                if mid:
                    u = conn.execute(
                        """
                        UPDATE tasks SET locked_by = NULL, locked_at = NULL,
                            status = ?, updated_at = ?
                        WHERE id = ? AND locked_by = ?
                        """,
                        (TaskStatus.PENDING.value, now.isoformat(), tid, mid),
                    )
                    cleared += u.rowcount
        return cleared

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        keys = row.keys()
        return Task(
            id=str(row["id"]),
            title=str(row["title"]),
            description=row["description"],
            project_id=row["project_id"],
            team_scope=row["team_scope"],
            organization_id=row["organization_id"] if "organization_id" in keys else None,
            team_id=row["team_id"] if "team_id" in keys else None,
            assigned_to=row["assigned_to"],
            assigned_by=row["assigned_by"],
            status=TaskStatus(str(row["status"])),
            locked_by=row["locked_by"],
            locked_at=_parse_dt(row["locked_at"]),
            parent_task_id=row["parent_task_id"],
            goal_link=row["goal_link"],
            created_at=_parse_dt(row["created_at"]) or datetime.now(timezone.utc),
            updated_at=_parse_dt(row["updated_at"]) or datetime.now(timezone.utc),
            completed_at=_parse_dt(row["completed_at"]),
            order_index=int(row["order_index"] or 0),
        )


class MissionControlStateStore(MissionControlStoreBase):
    """Per-chat active Mission Control project id."""

    def get_current_project_id(self, team_scope: str) -> str | None:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT current_project_id FROM mission_control_state WHERE team_scope = ?",
                (team_scope,),
            )
            row = cur.fetchone()
        if not row or not row["current_project_id"]:
            return None
        return str(row["current_project_id"])

    def set_current_project_id(self, team_scope: str, project_id: str | None) -> None:
        with self._connect() as conn:
            if project_id is None:
                conn.execute("DELETE FROM mission_control_state WHERE team_scope = ?", (team_scope,))
                return
            conn.execute(
                """
                INSERT INTO mission_control_state (team_scope, current_project_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(team_scope) DO UPDATE SET
                    current_project_id = excluded.current_project_id,
                    updated_at = excluded.updated_at
                """,
                (team_scope, project_id, _utcnow_iso()),
            )


class MobilePushTokenStore(MissionControlStoreBase):
    """FCM / device tokens for mobile push (Phase 34)."""

    def upsert(self, user_id: str, push_token: str, platform: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mobile_push_tokens (user_id, push_token, platform, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    push_token = excluded.push_token,
                    platform = excluded.platform,
                    updated_at = excluded.updated_at
                """,
                (user_id, push_token, platform, _utcnow_iso()),
            )


__all__ = [
    "MissionControlStateStore",
    "MobilePushTokenStore",
    "ProjectStore",
    "TaskStore",
]
