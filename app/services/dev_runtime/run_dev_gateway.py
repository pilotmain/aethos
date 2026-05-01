"""Gateway shortcut: ``run dev`` / ``run dev: …`` → :func:`run_dev_mission` when unambiguous."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.services.dev_runtime.service import run_dev_mission
from app.services.dev_runtime.workspace import list_workspaces


def parse_run_dev_goal(text: str) -> str | None:
    """
    If ``text`` starts a ``run dev`` command, return the goal string (possibly empty).

    Returns ``None`` when the message is not a run-dev command (caller should try mission parser).
    Does **not** match unrelated phrases like ``run developer``.
    """
    raw = (text or "").strip()
    low = raw.lower()
    prefix = "run dev"
    if not low.startswith(prefix):
        return None
    tail = raw[len(prefix) :]
    if low == prefix:
        return ""
    if tail.startswith(":"):
        return tail[1:].lstrip()
    if tail[:1] in (" ", "\t", "\n"):
        return tail.lstrip()
    # e.g. ``run developer…`` — not our command
    return None


def _format_dev_run_chat(res: dict[str, Any]) -> str:
    rid = str(res.get("run_id") or "")
    if res.get("ok"):
        parts = [
            f"Dev run completed (`{rid}`).",
            f"Iterations: {res.get('iterations')}, tests passed: {res.get('tests_passed')}, adapter: {res.get('adapter_used')}.",
        ]
        if res.get("pr_ready"):
            parts.append("PR-ready signal is true — review Mission Control for details.")
        return " ".join(parts)
    err = res.get("error") or res.get("status") or "failed"
    tail = json.dumps(res.get("steps") or [], default=str)[:1200]
    return f"Dev run did not complete cleanly (`{rid}`): {err}. Steps (truncated): {tail}"


def handle_run_dev_gateway(text: str, user_id: str, db: Session) -> dict[str, Any] | None:
    """
    If ``text`` is a ``run dev`` message, run or explain dev runtime; otherwise ``None``.

    Must run **before** :func:`~app.services.missions.parser.parse_mission` so
    ``run dev: …`` is not interpreted as a loose ``Role: task`` mission line.
    """
    goal_field = parse_run_dev_goal(text)
    if goal_field is None:
        return None

    if not goal_field:
        return {
            "mode": "chat",
            "text": (
                "Add a goal after `run dev:` — for example: `run dev: fix failing tests` "
                "with a dev workspace registered at POST /api/v1/dev/workspaces."
            ),
        }

    rows = list_workspaces(db, user_id)
    if not rows:
        return {
            "mode": "chat",
            "text": (
                "No dev workspaces yet. Register one with POST /api/v1/dev/workspaces (repo path), "
                "then use `run dev: …` again or POST /api/v1/dev/runs."
            ),
        }

    if len(rows) > 1:
        bits = [f"{w.name or 'workspace'} ({w.id[:8]}…)" for w in rows[:8]]
        extra = f" (+{len(rows) - 8} more)" if len(rows) > 8 else ""
        return {
            "mode": "chat",
            "text": (
                f"You have {len(rows)} dev workspaces — pick one for POST /api/v1/dev/runs "
                f"(workspace_id + goal). Registered: {', '.join(bits)}{extra}."
            ),
        }

    wid = rows[0].id
    res = run_dev_mission(db, user_id, wid, goal_field)
    return {
        "mode": "chat",
        "text": _format_dev_run_chat(res),
        "dev_run": res,
    }


__all__ = ["handle_run_dev_gateway", "parse_run_dev_goal"]
