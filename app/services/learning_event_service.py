# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LearningEvent


def list_pending(db: Session, user_id: str, limit: int = 20) -> list[LearningEvent]:
    st = (
        select(LearningEvent)
        .where(
            LearningEvent.user_id == user_id,
            LearningEvent.status == "pending",
        )
        .order_by(LearningEvent.id.desc())
        .limit(limit)
    )
    return list(db.scalars(st).all())


def get_for_user(
    db: Session, user_id: str, event_id: int
) -> LearningEvent | None:
    e = db.get(LearningEvent, event_id)
    if not e or e.user_id != user_id:
        return None
    return e


def approve(
    db: Session, user_id: str, event_id: int, *, apply_to_memory: bool, memory_service
) -> str | None:
    from app.services.audit_service import audit

    e = get_for_user(db, user_id, event_id)
    if not e or e.applied or (getattr(e, "status", "pending") != "pending"):
        return None
    e.approved = True
    e.applied = True
    e.status = "applied"
    rule = (e.proposed_rule or e.observation or "").strip()
    if rule and apply_to_memory:
        memory_service.remember_note(
            db,
            user_id,
            f"Approved learning: {rule}",
            category="user_note",
            source="learning_event",
        )
        try:
            from app.services.system_memory_files import append_memory_entry

            line = rule if len(rule) <= 600 else rule[:600] + "…"
            append_memory_entry(
                f"Approved learning #{e.id} ({e.agent_key}): {line}",
                source="learning_approved",
            )
        except ValueError:
            pass
    msg = (rule or "approved")[:2000]
    audit(
        db,
        event_type="learning.approved",
        actor="user",
        user_id=user_id,
        job_id=None,
        message=msg,
        metadata={"event_id": e.id, "agent_key": e.agent_key},
    )
    return f"Learning #{e.id} approved" + (f" and saved a memory line." if rule and apply_to_memory else ".")


def reject(
    db: Session, user_id: str, event_id: int
) -> str | None:
    from app.services.audit_service import audit

    e = get_for_user(db, user_id, event_id)
    if not e or e.applied or (getattr(e, "status", "pending") != "pending"):
        return None
    e.applied = True
    e.approved = False
    e.status = "rejected"
    audit(
        db,
        event_type="learning.rejected",
        actor="user",
        user_id=user_id,
        job_id=None,
        message=f"rejected event #{e.id}",
        metadata={"event_id": e.id},
    )
    return f"Learning #{e.id} rejected."


def record_suggestion(
    db: Session,
    *,
    user_id: str | None,
    agent_key: str,
    observation: str,
    proposed_rule: str | None = None,
    event_type: str = "suggestion",
) -> LearningEvent:
    ev = LearningEvent(
        user_id=user_id,
        agent_key=agent_key,
        event_type=event_type,
        observation=observation[:20_000],
        proposed_rule=(proposed_rule or "")[:20_000] or None,
        approved=False,
        applied=False,
        status="pending",
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev
