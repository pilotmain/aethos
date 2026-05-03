"""DB-backed steering for :class:`~app.models.dev_runtime.NexaDevRun`."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.dev_runtime import NexaDevRun


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def cancel_run(db: Session, run_id: str, user_id: str) -> NexaDevRun | None:
    r = db.get(NexaDevRun, run_id)
    if not r or r.user_id != user_id:
        return None
    if r.status in ("completed", "failed", "cancelled"):
        return r
    r.status = "cancelled"
    r.completed_at = _utc_now()
    r.error = (r.error or "")[:2000] or "cancelled_by_user"
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def pause_run(db: Session, run_id: str, user_id: str) -> NexaDevRun | None:
    r = db.get(NexaDevRun, run_id)
    if not r or r.user_id != user_id:
        return None
    if r.status not in ("queued", "running"):
        return r
    r.status = "paused"
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def resume_run(db: Session, run_id: str, user_id: str) -> NexaDevRun | None:
    r = db.get(NexaDevRun, run_id)
    if not r or r.user_id != user_id:
        return None
    if r.status == "paused":
        r.status = "queued"
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def edit_run_goal(db: Session, run_id: str, user_id: str, new_goal: str) -> NexaDevRun | None:
    r = db.get(NexaDevRun, run_id)
    if not r or r.user_id != user_id:
        return None
    if r.status in ("completed", "failed", "cancelled"):
        return r
    r.goal = (new_goal or "")[:12000]
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


__all__ = ["cancel_run", "edit_run_goal", "pause_run", "resume_run"]
