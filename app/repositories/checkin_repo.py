# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import CheckIn


class CheckInRepository:
    def create(self, db: Session, user_id: str, task_id: int, prompt_text: str, scheduled_for: datetime) -> CheckIn:
        row = CheckIn(user_id=user_id, task_id=task_id, prompt_text=prompt_text, scheduled_for=scheduled_for)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def list_pending(self, db: Session, user_id: str) -> list[CheckIn]:
        stmt = (
            select(CheckIn)
            .where(CheckIn.user_id == user_id)
            .where(CheckIn.status.in_(["scheduled", "sent"]))
            .order_by(CheckIn.scheduled_for.asc())
        )
        return list(db.scalars(stmt).all())

    def list_due_unsent(self, db: Session, now: datetime) -> list[CheckIn]:
        stmt = (
            select(CheckIn)
            .where(CheckIn.status == "scheduled")
            .where(CheckIn.scheduled_for <= now)
            .order_by(CheckIn.scheduled_for.asc())
        )
        return list(db.scalars(stmt).all())

    def get_for_user(self, db: Session, checkin_id: int, user_id: str) -> CheckIn | None:
        return db.scalar(select(CheckIn).where(CheckIn.id == checkin_id, CheckIn.user_id == user_id))

    def mark_sent(self, db: Session, row: CheckIn, now: datetime) -> CheckIn:
        row.sent_at = now
        row.status = "sent"
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def respond(self, db: Session, row: CheckIn, response_text: str, response_type: str) -> CheckIn:
        row.response_text = response_text
        row.response_type = response_type
        row.status = "responded"
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def cancel_for_task_ids(self, db: Session, user_id: str, task_ids: list[int]) -> int:
        if not task_ids:
            return 0
        stmt = (
            update(CheckIn)
            .where(CheckIn.user_id == user_id)
            .where(CheckIn.task_id.in_(task_ids))
            .where(CheckIn.status.in_(["scheduled", "sent"]))
            .values(status="cancelled")
        )
        result = db.execute(stmt)
        db.commit()
        return int(result.rowcount or 0)

    def cancel_for_task_ids_return_ids(self, db: Session, user_id: str, task_ids: list[int]) -> list[int]:
        if not task_ids:
            return []
        rows = list(
            db.scalars(
                select(CheckIn)
                .where(CheckIn.user_id == user_id)
                .where(CheckIn.task_id.in_(task_ids))
                .where(CheckIn.status.in_(["scheduled", "sent"]))
                .order_by(CheckIn.id.asc())
            ).all()
        )
        ids = [row.id for row in rows]
        if not rows:
            return []
        for row in rows:
            row.status = "cancelled"
            db.add(row)
        db.commit()
        return ids

    def cancel_matching_query_return_ids(self, db: Session, user_id: str, query: str) -> list[int]:
        q = (query or "").strip().lower()
        if not q:
            return []
        rows = list(
            db.scalars(
                select(CheckIn)
                .where(CheckIn.user_id == user_id)
                .where(CheckIn.status.in_(["scheduled", "sent"]))
                .order_by(CheckIn.id.asc())
            ).all()
        )
        matched = [row for row in rows if q in (row.prompt_text or "").lower()]
        if not matched:
            return []
        ids = [row.id for row in matched]
        for row in matched:
            row.status = "cancelled"
            db.add(row)
        db.commit()
        return ids

    def cancel_for_user(self, db: Session, user_id: str, checkin_id: int) -> CheckIn | None:
        row = self.get_for_user(db, checkin_id, user_id)
        if not row:
            return None
        row.status = "cancelled"
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
