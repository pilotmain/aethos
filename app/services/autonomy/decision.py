"""Phase 44A — autonomous decision loop: signals → prioritized NexaTask candidates → persistence."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.autonomy import NexaAutonomousTask, NexaAutonomyDecisionLog
from app.models.dev_runtime import NexaDevRun
from app.models.nexa_next_runtime import NexaMission
from app.services.autonomy.intelligence import build_intelligent_context
from app.services.autonomy.prioritize import prioritize_tasks
from app.services.events.unified_event import emit_unified_event
from app.services.memory.memory_store import MemoryStore
from app.services.tasks.unified_task import NexaTask


def _recent_user_ids(db: Session, *, limit: int = 5) -> list[str]:
    rows = list(
        db.scalars(select(NexaDevRun.user_id).order_by(desc(NexaDevRun.created_at)).limit(120)).all()
    )
    out: list[str] = []
    for uid in rows:
        u = (uid or "").strip()
        if u and u not in out:
            out.append(u)
        if len(out) >= limit:
            break
    return out


def _pending_title_exists(db: Session, user_id: str, title: str) -> bool:
    t = title.strip()[:8000]
    if not t:
        return True
    row = db.scalar(
        select(NexaAutonomousTask).where(
            NexaAutonomousTask.user_id == user_id,
            NexaAutonomousTask.title == t,
            NexaAutonomousTask.state == "pending",
        )
    )
    return row is not None


def autonomous_decision_loop(
    db: Session,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Inspect recent failures, missions, and memory depth; enqueue prioritized autonomous tasks.

    When ``user_id`` is omitted, considers recent dev-run users (bounded fan-out).
    """
    if not getattr(get_settings(), "nexa_autonomous_mode", False):
        return {"ok": False, "skipped": True, "reason": "autonomous_mode_off"}

    uid0 = (user_id or "").strip()
    targets = [(uid0,)] if uid0 else [(u,) for u in _recent_user_ids(db)]
    if not targets:
        return {"ok": True, "users": [], "generated_task_ids": [], "detail": "no_recent_users"}

    aggregate_ids: list[str] = []
    per_user: list[dict[str, Any]] = []

    for (uid,) in targets:
        uid = uid.strip()
        if not uid:
            continue

        failed_runs = list(
            db.scalars(
                select(NexaDevRun)
                .where(NexaDevRun.user_id == uid, NexaDevRun.status.in_(("failed", "blocked")))
                .order_by(desc(NexaDevRun.created_at))
                .limit(6)
            ).all()
        )
        running_missions = list(
            db.scalars(
                select(NexaMission)
                .where(NexaMission.user_id == uid, NexaMission.status == "running")
                .order_by(desc(NexaMission.created_at))
                .limit(5)
            ).all()
        )

        mem_count = len(MemoryStore().list_entries(uid, limit=120))

        candidates: list[NexaTask] = []
        if failed_runs:
            candidates.append(
                NexaTask(
                    id=str(uuid.uuid4()),
                    type="dev",
                    input="Fix failing tests from recent dev runs",
                    context={"signal": "failed_dev_runs", "run_ids": [r.id for r in failed_runs[:5]]},
                    priority=92,
                    auto_generated=True,
                    origin="autonomy",
                )
            )
            candidates.append(
                NexaTask(
                    id=str(uuid.uuid4()),
                    type="dev",
                    input="Review recent changes and stabilize CI",
                    context={"signal": "failed_dev_follow_up"},
                    priority=78,
                    auto_generated=True,
                    origin="autonomy",
                )
            )

        for m in running_missions:
            candidates.append(
                NexaTask(
                    id=str(uuid.uuid4()),
                    type="mission",
                    input=f"Continue mission: {(m.title or '')[:400]}",
                    context={"mission_id": m.id, "signal": "running_mission"},
                    priority=74,
                    auto_generated=True,
                    origin="autonomy",
                )
            )

        if mem_count >= 18:
            nt = NexaTask(
                id=str(uuid.uuid4()),
                type="system",
                input="Summarize persistent memory and prune stale notes",
                context={"signal": "memory_depth", "approx_entries": mem_count},
                priority=55,
                auto_generated=True,
                origin="autonomy",
            )
            intel = build_intelligent_context(nt, user_id=uid, max_chars=1200)
            nt.context["intelligent_context"] = intel
            candidates.append(nt)

        if not candidates:
            summary = "No actionable signals this cycle"
            log = NexaAutonomyDecisionLog(
                id=str(uuid.uuid4()),
                user_id=uid,
                summary=summary,
                detail_json=json.dumps({"signals": {"failed_runs": len(failed_runs), "running_missions": len(running_missions), "memory_entries": mem_count}}),
            )
            db.add(log)
            db.commit()
            per_user.append({"user_id": uid, "generated": [], "summary": summary})
            continue

        ordered = prioritize_tasks(candidates)
        inserted: list[str] = []
        for t in ordered[:3]:
            title = t.input.strip()[:8000]
            if _pending_title_exists(db, uid, title):
                continue
            tid = str(uuid.uuid4())
            row = NexaAutonomousTask(
                id=tid,
                user_id=uid,
                title=title,
                state="pending",
                priority=min(100, max(0, int(t.priority))),
                auto_generated=True,
                origin="autonomy",
                context_json=json.dumps(
                    {"nexa_task": {"type": t.type, "context": t.context}, "decision": "autonomous_decision_loop"},
                    ensure_ascii=False,
                )[:50_000],
            )
            db.add(row)
            inserted.append(tid)
        db.commit()

        detail_obj = {
            "failed_dev_runs": len(failed_runs),
            "running_missions": len(running_missions),
            "memory_entries": mem_count,
            "queued": inserted,
        }
        log = NexaAutonomyDecisionLog(
            id=str(uuid.uuid4()),
            user_id=uid,
            summary=f"Queued {len(inserted)} autonomous tasks",
            detail_json=json.dumps(detail_obj, ensure_ascii=False),
        )
        db.add(log)
        db.commit()

        emit_unified_event(
            "autonomy.decision.completed",
            task_id=log.id,
            user_id=uid,
            payload={"queued": len(inserted), "user_id": uid},
        )
        aggregate_ids.extend(inserted)
        goal_ids: list[str] = []
        try:
            from app.services.autonomy.goal_engine import generate_and_persist_goals

            goal_ids = generate_and_persist_goals(db, uid)
            aggregate_ids.extend(goal_ids)
        except Exception:
            pass
        per_user.append(
            {
                "user_id": uid,
                "generated": inserted,
                "summary": log.summary,
                "goal_engine_ids": goal_ids,
            }
        )

    return {
        "ok": True,
        "generated_task_ids": aggregate_ids,
        "users": per_user,
    }


__all__ = ["autonomous_decision_loop"]
