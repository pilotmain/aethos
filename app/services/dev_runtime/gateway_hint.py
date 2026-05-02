"""Optional chat path when text looks like a dev task — prefer execution over REST hints (Phase 51)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dev_runtime import NexaDevWorkspace
from app.services.dev_runtime.run_dev_gateway import format_dev_run_summary
from app.services.dev_runtime.service import run_dev_mission
from app.services.dev_runtime.workspace import list_workspaces


def maybe_dev_gateway_hint(text: str, user_id: str, db: Session) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if len(raw) < 8:
        return None
    low = raw.lower()
    cues = (
        "fix failing",
        "failing test",
        "run test",
        "build feature",
        "review code",
        "prepare pr",
        "open pr",
        "git ",
        "pytest",
        "npm test",
    )
    if not any(c in low for c in cues):
        return None

    n = db.scalar(
        select(func.count()).select_from(NexaDevWorkspace).where(NexaDevWorkspace.user_id == user_id)
    )
    if not n:
        return {
            "mode": "chat",
            "text": (
                "I can investigate this, but I need a workspace first. "
                "Add or select your repo in Mission Control, then say “run dev: investigate this” "
                "with the specifics you care about."
            ),
            "dev_routing_hint": True,
        }

    rows = list_workspaces(db, user_id)
    if len(rows) > 1:
        lines = [f"- {(w.name or w.id[:8]).strip()}" for w in rows[:16]]
        more = len(rows) - 16
        tail = f"\n… and {more} more." if more > 0 else ""
        return {
            "mode": "chat",
            "text": (
                "I can run this. Which workspace should I use?\n"
                + "\n".join(lines)
                + tail
            ),
            "dev_routing_hint": True,
        }

    wid = rows[0].id
    goal = raw[:8000]
    res = run_dev_mission(db, user_id, wid, goal)
    return {
        "mode": "chat",
        "text": format_dev_run_summary(res),
        "dev_run": res,
        "intent": "dev_mission",
    }


__all__ = ["maybe_dev_gateway_hint"]
