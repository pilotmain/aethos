"""Optional chat hint when text looks like a dev task and workspaces exist."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dev_runtime import NexaDevWorkspace


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
        return None

    return {
        "mode": "chat",
        "text": (
            "Dev mission detected. Register a repo with POST /api/v1/dev/workspaces, then start a run with "
            "POST /api/v1/dev/runs (workspace_id + goal). Mission Control includes a Dev workspace panel when configured."
        ),
        "dev_routing_hint": True,
    }


__all__ = ["maybe_dev_gateway_hint"]
