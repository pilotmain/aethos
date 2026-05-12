# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import UserMemory
from app.repositories.checkin_repo import CheckInRepository
from app.repositories.memory_repo import MemoryRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.memory import (
    AgentMemoryState,
    MemoryForgetResult,
    MemoryNoteRead,
    PreferencesRead,
    PreferencesUpdate,
)

_DEFAULT_SOUL = """# Soul

You are AethOS — a multi-agent execution system that routes work to specialized agents when needed.

## Purpose
- Help the user feel calmer, clearer, and more capable.
- Reduce chaos into a short, realistic next-step plan.
- Remember stable preferences and useful context.

## Rules
- Be warm, concise, and practical.
- Prefer the smallest next action that creates momentum.
- Do not keep reminding the user about something they asked to forget or remove.
- Respect explicit user preferences and corrections.
- When a memory is outdated or the user revokes it, remove it.
"""


class MemoryService:
    def __init__(self) -> None:
        self.repo = MemoryRepository()
        self.task_repo = TaskRepository()
        self.checkin_repo = CheckInRepository()
        self.settings = get_settings()

    def get_preferences(self, db: Session, user_id: str) -> PreferencesRead:
        row = self.repo.get(db, user_id, "preferences")
        if not row:
            return PreferencesRead(
                planning_style=self.settings.default_planning_style,
                max_daily_tasks=self.settings.default_max_tasks,
                typical_gym_days=[],
            )
        return PreferencesRead(**row.value_json)

    def update_preferences(self, db: Session, user_id: str, payload: PreferencesUpdate) -> PreferencesRead:
        current = self.get_preferences(db, user_id)
        data = current.model_dump()
        data.update({k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None})
        row = self.repo.upsert(db, user_id, "preferences", data, source="user")
        return PreferencesRead(**row.value_json)

    def get_learned_preferences(self, db: Session, user_id: str) -> dict[str, str]:
        """String flags from user_memory (keys like learned:avoids_calls). For prompts, not PII."""
        rows = list(
            db.scalars(
                select(UserMemory).where(
                    UserMemory.user_id == user_id,
                    UserMemory.key.startswith("learned:"),
                )
            ).all()
        )
        out: dict[str, str] = {}
        for row in rows:
            v = (row.value_json or {}).get("value")
            if v is not None and str(v).strip() != "":
                out[row.key] = str(v)
        return out

    def save_learned_flag(
        self, db: Session, user_id: str, key: str, value: str, source: str = "system"
    ) -> None:
        """e.g. save_learned_flag(db, uid, 'learned:avoids_calls', 'true')"""
        key = key if key.startswith("learned:") else f"learned:{key}"
        self.repo.upsert(db, user_id, key, {"value": value}, source=source)

    def get_soul_markdown(self, db: Session, user_id: str) -> str:
        row = self.repo.get(db, user_id, "agent:soul")
        if not row:
            return _DEFAULT_SOUL
        return str((row.value_json or {}).get("content") or _DEFAULT_SOUL)

    def update_soul_markdown(self, db: Session, user_id: str, content: str, source: str = "user") -> str:
        cleaned = content.strip()
        if not cleaned.startswith("#"):
            cleaned = "# Soul\n\n" + cleaned
        self.repo.upsert(db, user_id, "agent:soul", {"content": cleaned}, source=source)
        return cleaned

    def remember_note(
        self,
        db: Session,
        user_id: str,
        content: str,
        *,
        category: str = "note",
        source: str = "user",
    ) -> MemoryNoteRead:
        cleaned = content.strip()
        slug = re.sub(r"[^a-z0-9]+", "-", cleaned.lower()).strip("-")[:40] or uuid.uuid4().hex[:8]
        key = f"memory:{category}:{slug}:{uuid.uuid4().hex[:6]}"
        summary = cleaned if len(cleaned) <= 120 else cleaned[:117] + "..."
        row = self.repo.upsert(
            db,
            user_id,
            key,
            {"category": category, "content": cleaned, "summary": summary},
            source=source,
        )
        return self._to_note(row)

    def list_notes(self, db: Session, user_id: str) -> list[MemoryNoteRead]:
        return [self._to_note(row) for row in self.repo.list_for_user(db, user_id, prefix="memory:")]

    def update_note(
        self,
        db: Session,
        user_id: str,
        key: str,
        content: str,
        *,
        category: str | None = None,
        source: str = "user",
    ) -> MemoryNoteRead:
        row = self.repo.get(db, user_id, key)
        if not row or not key.startswith("memory:"):
            raise ValueError("Memory note not found")
        cleaned = content.strip()
        data = dict(row.value_json or {})
        if category:
            data["category"] = category
        data["content"] = cleaned
        data["summary"] = cleaned if len(cleaned) <= 120 else cleaned[:117] + "..."
        updated = self.repo.upsert(db, user_id, key, data, source=source)
        return self._to_note(updated)

    def delete_note(self, db: Session, user_id: str, key: str) -> bool:
        row = self.repo.get(db, user_id, key)
        if not row or not key.startswith("memory:"):
            return False
        self.repo.delete(db, row)
        return True

    def get_memory_markdown(self, db: Session, user_id: str) -> str:
        notes = self.list_notes(db, user_id)
        if not notes:
            return "# Memory\n\n_No saved memory yet._\n"
        lines = ["# Memory", ""]
        for note in notes:
            lines.append(f"- [{note.category}] {note.content}")
        lines.append("")
        return "\n".join(lines)

    def get_state(self, db: Session, user_id: str) -> AgentMemoryState:
        notes = self.list_notes(db, user_id)
        return AgentMemoryState(
            preferences=self.get_preferences(db, user_id),
            soul_markdown=self.get_soul_markdown(db, user_id),
            memory_markdown=self.get_memory_markdown(db, user_id),
            notes=notes,
        )

    def forget(self, db: Session, user_id: str, query: str) -> MemoryForgetResult:
        cleaned = query.strip()
        note_rows = self.repo.search_notes(db, user_id, cleaned)
        deleted_notes = self.repo.delete_many(db, user_id, [row.key for row in note_rows])

        matching_tasks = self.task_repo.list_matching_for_user(db, user_id, cleaned)
        task_ids = [task.id for task in matching_tasks]
        task_titles = [task.title for task in matching_tasks]
        cancelled_ids = self.checkin_repo.cancel_for_task_ids_return_ids(db, user_id, task_ids)
        extra_cancelled_ids = self.checkin_repo.cancel_matching_query_return_ids(db, user_id, cleaned)
        all_cancelled_ids = sorted(set(cancelled_ids + extra_cancelled_ids))
        for task in matching_tasks:
            self.task_repo.delete(db, task)

        return MemoryForgetResult(
            deleted_notes=deleted_notes,
            deleted_tasks=len(task_ids),
            cancelled_checkins=len(all_cancelled_ids),
            query=cleaned,
            deleted_task_ids=task_ids,
            cancelled_checkin_ids=all_cancelled_ids,
            deleted_task_titles=task_titles,
        )

    def _to_note(self, row: UserMemory) -> MemoryNoteRead:
        data = row.value_json or {}
        return MemoryNoteRead(
            key=row.key,
            category=str(data.get("category") or "note"),
            content=str(data.get("content") or ""),
            summary=str(data.get("summary") or data.get("content") or ""),
            source=row.source,
        )
