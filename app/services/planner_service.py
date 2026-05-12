# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models import Plan, Task
from app.repositories.plan_repo import PlanRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.memory import PreferencesRead


@dataclass
class PlannedTask:
    task: Task
    reason: str
    display_order: int


def _category_rank(category: str) -> int:
    """When priority scores tie, prefer work/admin over social/personal."""
    order = {"work": 5, "admin": 4, "health": 3, "personal": 2, "general": 1}
    return order.get(category, 0)


class PlannerService:
    def __init__(self) -> None:
        self.plan_repo = PlanRepository()
        self.task_repo = TaskRepository()

    def build_plan(
        self,
        db: Session,
        user_id: str,
        plan_date: date,
        tasks: list[Task],
        detected_state: str,
        preferences: PreferencesRead,
        source_brain_dump_id: str | None = None,
    ) -> Plan:
        mode = detected_state
        max_tasks = 3 if mode == "overwhelm" else preferences.max_daily_tasks
        selected = self._rank_and_select(tasks, max_tasks=max_tasks, mode=mode)
        summary = self._summary_for_mode(mode, preferences.planning_style, len(selected))
        plan = self.plan_repo.create(
            db,
            user_id=user_id,
            plan_date=plan_date,
            summary=summary,
            mode=mode,
            source_brain_dump_id=source_brain_dump_id,
        )
        task_reasons = [(item.task.id, item.display_order, item.reason) for item in selected]
        self.plan_repo.replace_plan_tasks(db, plan.id, task_reasons)
        return plan

    def serialize_plan(self, db: Session, plan: Plan) -> dict:
        rows = self.plan_repo.get_task_rows(db, plan.id)
        tasks = []
        reasons = []
        for plan_task, task in rows:
            tasks.append(task)
            reasons.append({
                "task_id": task.id,
                "reason": plan_task.reason,
                "display_order": plan_task.display_order,
            })
        return {"plan": plan, "tasks": tasks, "reasons": reasons}

    def _rank_and_select(self, tasks: list[Task], max_tasks: int, mode: str) -> list[PlannedTask]:
        sorted_tasks = sorted(
            tasks,
            key=lambda t: (t.priority_score, _category_rank(t.category), t.created_at),
            reverse=True,
        )
        selected = []
        for idx, task in enumerate(sorted_tasks[:max_tasks], start=1):
            reason = self._reason(task, idx, mode)
            selected.append(PlannedTask(task=task, reason=reason, display_order=idx))
        return selected

    def _reason(self, task: Task, idx: int, mode: str) -> str:
        if idx == 1:
            return "Highest urgency and likely to reduce mental load fastest."
        if task.category == "work":
            return "Important work item that may be blocking progress."
        if task.category == "admin":
            return "Likely time-sensitive life admin task."
        if mode == "overwhelm":
            return "Kept because it is manageable and helps reduce pressure."
        return "Worth doing today based on priority and momentum."

    def _summary_for_mode(self, mode: str, planning_style: str, count: int) -> str:
        if mode == "overwhelm":
            return (
                "A calmer, smaller set for what you can handle right now."
                if planning_style == "gentle"
                else "Reset: these are the core items only today."
            )
        return f"Here's a calm focus list for today — {count} steps, kept small on purpose."
