# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Plan, PlanTask, Task


class PlanRepository:
    def create(self, db: Session, user_id: str, plan_date: date, summary: str, mode: str, source_brain_dump_id: str | None = None) -> Plan:
        plan = Plan(user_id=user_id, plan_date=plan_date, summary=summary, mode=mode, source_brain_dump_id=source_brain_dump_id)
        db.add(plan)
        db.commit()
        db.refresh(plan)
        return plan

    def replace_plan_tasks(self, db: Session, plan_id: str, task_reasons: list[tuple[int, int, str | None]]) -> None:
        existing = db.scalars(select(PlanTask).where(PlanTask.plan_id == plan_id)).all()
        for row in existing:
            db.delete(row)
        db.flush()
        for task_id, display_order, reason in task_reasons:
            db.add(PlanTask(plan_id=plan_id, task_id=task_id, display_order=display_order, reason=reason))
        db.commit()

    def get_for_day(self, db: Session, user_id: str, plan_date: date) -> Plan | None:
        return db.scalar(select(Plan).where(Plan.user_id == user_id, Plan.plan_date == plan_date).order_by(Plan.created_at.desc()))

    def get_task_rows(self, db: Session, plan_id: str) -> list[tuple[PlanTask, Task]]:
        stmt = (
            select(PlanTask, Task)
            .join(Task, Task.id == PlanTask.task_id)
            .where(PlanTask.plan_id == plan_id)
            .order_by(PlanTask.display_order.asc())
        )
        return list(db.execute(stmt).all())
