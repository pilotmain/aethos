import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Plan, Task
from app.repositories.task_repo import TaskRepository
from app.schemas.memory import PreferencesRead
from app.schemas.task import TaskCreate
from app.services.checkin_service import CheckInService
from app.services.dump_service import DumpService
from app.services.intent_service import is_valid_task, normalize_task
from app.services.llm_service import LLMService
from app.services.memory_service import MemoryService
from app.services.planner_service import PlannerService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


def _short_deferred_label(title: str) -> str:
    t = title.strip()
    lower = t.lower()
    if lower.startswith("go to "):
        rest = t[6:].strip()
        return rest[:1].upper() + rest[1:] if rest else t
    if lower.startswith("go "):
        rest = t[3:].strip()
        return rest[:1].upper() + rest[1:] if rest else t
    return t[:1].upper() + t[1:] if t else title


class OrchestratorService:
    def __init__(self) -> None:
        self.users = UserService()
        self.dumps = DumpService()
        self.memory = MemoryService()
        self.llm = LLMService()
        self.tasks = TaskRepository()
        self.planner = PlannerService()
        self.checkins = CheckInService()

    def generate_plan_from_text(
        self,
        db: Session,
        user_id: str,
        text: str,
        input_source: str = "text",
        intent: str | None = None,
    ) -> dict:
        if intent is not None and intent != "brain_dump":
            logger.error("Blocked plan generation for non-brain_dump intent=%s", intent)
            return {
                "needs_more_context": True,
                "plan": None,
                "detected_state": "normal",
                "extracted_tasks_count": 0,
            }
        user = self.users.get_or_create(db, user_id)
        prefs = self.memory.get_preferences(db, user_id)
        extracted = self.llm.extract_tasks(text=text, now=datetime.now(UTC).replace(tzinfo=None))
        prov = []
        if self.llm.client:
            prov.append("anthropic")
        if self.llm.openai_client:
            prov.append("openai")
        logger.info(
            "task extraction use_real_llm=%s providers=%s",
            self.llm.settings.use_real_llm,
            ",".join(prov) if prov else "none",
        )

        extracted["tasks"] = self._normalize_extracted_tasks(extracted.get("tasks", []), fallback_text=text)
        if not extracted["tasks"]:
            detected_state = extracted.get("detected_state") or self.llm.detect_state(text)
            logger.info("generate_plan_from_text needs_more_context=true detected_state=%s", detected_state)
            return {
                "needs_more_context": True,
                "detected_state": detected_state,
                "extracted_tasks_count": 0,
            }

        detected_state = extracted.get("detected_state") or self.llm.detect_state(text)
        dump = self.dumps.create_dump(db, user_id, text, input_source, emotional_state=detected_state)
        tasks = self._materialize_tasks(db, user_id, dump.id, extracted.get("tasks", []))
        plan = self.planner.build_plan(
            db,
            user_id=user_id,
            plan_date=date.today(),
            tasks=tasks,
            detected_state=detected_state,
            preferences=prefs,
            source_brain_dump_id=dump.id,
        )
        self._maybe_refine_plan_copy(db, plan, detected_state)
        serialized = self.planner.serialize_plan(db, plan)
        self.checkins.schedule_for_tasks(db, user_id, serialized["tasks"], planning_style=prefs.planning_style)
        selected_ids = {t.id for t in serialized["tasks"]}
        deferred_lines = self._deferred_lines_for_plan(tasks, selected_ids, date.today())
        return {
            "needs_more_context": False,
            "plan": serialized,
            "detected_state": detected_state,
            "extracted_tasks_count": len(tasks),
            "deferred_lines": deferred_lines,
        }

    def get_today_plan(self, db: Session, user_id: str) -> dict | None:
        self.users.get_or_create(db, user_id)
        prefs = self.memory.get_preferences(db, user_id)
        plan = self.planner.plan_repo.get_for_day(db, user_id, date.today())
        if not plan:
            tasks = self.tasks.list_today(db, user_id, date.today())
            if not tasks:
                return None
            plan = self.planner.build_plan(
                db,
                user_id=user_id,
                plan_date=date.today(),
                tasks=tasks,
                detected_state="normal",
                preferences=prefs,
            )
        return self.planner.serialize_plan(db, plan)

    def _maybe_refine_plan_copy(self, db: Session, plan: Plan, detected_state: str) -> None:
        if not self.llm.settings.use_real_llm or (
            not self.llm.client and not self.llm.openai_client
        ):
            return
        rows = self.planner.plan_repo.get_task_rows(db, plan.id)
        titles = [task.title for _, task in rows]
        refined = self.llm.refine_plan_language(titles, detected_state)
        if not refined:
            return
        plan.summary = refined["summary"]
        db.add(plan)
        db.commit()
        db.refresh(plan)
        reasons = refined.get("reasons") or []
        task_reasons = []
        for i, (pt, task) in enumerate(rows):
            if i < len(reasons):
                rr = reasons[i]
                if isinstance(rr, str) and rr.strip():
                    r = rr.strip()
                else:
                    r = pt.reason
            else:
                r = pt.reason
            task_reasons.append((task.id, pt.display_order, r))
        self.planner.plan_repo.replace_plan_tasks(db, plan.id, task_reasons)

    def get_focus_task_title(self, db: Session, user_id: str) -> str | None:
        """Top task from today's plan, or next open task for today."""
        result = self.get_today_plan(db, user_id)
        if result and result.get("tasks"):
            return result["tasks"][0].title
        self.users.get_or_create(db, user_id)
        pending = self.tasks.list_today(db, user_id, date.today())
        return pending[0].title if pending else None

    def refresh_morning_plan(self, db: Session, user_id: str) -> dict | None:
        self.users.get_or_create(db, user_id)
        prefs = self.memory.get_preferences(db, user_id)
        tasks = self.tasks.list_today(db, user_id, date.today())
        if not tasks:
            return None
        plan = self.planner.build_plan(
            db,
            user_id=user_id,
            plan_date=date.today(),
            tasks=tasks,
            detected_state="normal",
            preferences=prefs,
        )
        return self.planner.serialize_plan(db, plan)

    def _normalize_extracted_tasks(self, raw_tasks: list[dict], fallback_text: str) -> list[dict]:
        out: list[dict] = []
        for item in raw_tasks:
            raw_title = item.get("title") or ""
            nt = normalize_task(raw_title)
            if not nt or not is_valid_task(nt):
                continue
            out.append({**item, "title": nt[:255]})
        if not out:
            nt = normalize_task(fallback_text)
            if nt and is_valid_task(nt):
                out.append(
                    {
                        "title": nt[:255],
                        "description": None,
                        "category": "general",
                        "priority_score": 50,
                        "due_at": None,
                        "suggested_for_date": None,
                    }
                )
        return out

    def _deferred_lines_for_plan(
        self, all_tasks: list[Task], selected_ids: set[int], today: date
    ) -> list[str]:
        lines: list[str] = []
        tomorrow = today + timedelta(days=1)
        for task in all_tasks:
            if task.id in selected_ids or not task.suggested_for_date:
                continue
            if task.suggested_for_date == tomorrow:
                label = _short_deferred_label(task.title)
                lines.append(f"{label} can stay planned for tomorrow.")
            elif task.suggested_for_date > today:
                lines.append(f"{task.title} can wait until later.")
        return lines

    def _materialize_tasks(self, db: Session, user_id: str, brain_dump_id: str, raw_tasks: list[dict]) -> list[Task]:
        rows = []
        for item in raw_tasks:
            payload = TaskCreate(
                title=item["title"],
                description=item.get("description"),
                category=item.get("category") or "general",
                priority_score=item.get("priority_score") or 50,
                due_at=item.get("due_at"),
                suggested_for_date=item.get("suggested_for_date"),
            )
            rows.append(Task(user_id=user_id, brain_dump_id=brain_dump_id, **payload.model_dump()))
        return self.tasks.save_many(db, rows)
