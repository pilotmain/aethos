# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Focus-task loop detection and task-pattern stats for adaptive nudge/unstick copy."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TaskPattern, User


def detect_stuck_loop(user: User | None, current_task: str | None) -> bool:
    if not current_task or not user:
        return False
    if not user.last_focus_task:
        return False
    if user.last_focus_task != current_task:
        return False
    return user.focus_attempts >= 2


def touch_user_interaction(db: Session, user: User) -> None:
    user.last_interaction_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)


def reset_focus_after_completion(db: Session, user: User, completed_task_title: str | None) -> None:
    user.last_focus_task = None
    user.focus_attempts = 0
    db.add(user)
    if completed_task_title:
        _bump_task_pattern_completed(db, user.id, completed_task_title)
    db.commit()
    db.refresh(user)


def _bump_task_pattern_completed(db: Session, user_id: str, task_title: str) -> None:
    row = db.scalar(
        select(TaskPattern).where(
            TaskPattern.user_id == user_id,
            TaskPattern.task_title == task_title,
        )
    )
    if row:
        row.times_completed += 1
        db.add(row)
    else:
        db.add(
            TaskPattern(
                user_id=user_id,
                task_title=task_title,
                times_attempted=0,
                times_completed=1,
            )
        )


def update_focus_after_nudge_or_unstick(db: Session, user: User, focus_task: str | None) -> None:
    if not focus_task:
        return
    if user.last_focus_task == focus_task:
        user.focus_attempts += 1
    else:
        user.last_focus_task = focus_task
        user.focus_attempts = 1
    db.add(user)
    _bump_task_pattern_attempted(db, user.id, focus_task)
    db.commit()
    db.refresh(user)


def _bump_task_pattern_attempted(db: Session, user_id: str, task_title: str) -> None:
    row = db.scalar(
        select(TaskPattern).where(
            TaskPattern.user_id == user_id,
            TaskPattern.task_title == task_title,
        )
    )
    if row:
        row.times_attempted += 1
        db.add(row)
    else:
        db.add(
            TaskPattern(
                user_id=user_id,
                task_title=task_title,
                times_attempted=1,
                times_completed=0,
            )
        )
