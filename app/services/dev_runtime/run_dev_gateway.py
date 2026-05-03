"""Gateway shortcut: ``run dev`` / ``run dev: …`` → :func:`run_dev_mission` when unambiguous."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.services.dev_runtime.service import run_dev_mission
from app.services.dev_runtime.workspace import list_workspaces
from app.services.gateway.context import GatewayContext


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


def format_dev_run_summary(res: dict[str, Any]) -> str:
    rid = str(res.get("run_id") or "")
    prog = res.get("progress_messages") or []
    head = ""
    if isinstance(prog, list) and prog:
        head = "\n".join(f"→ {p}" for p in prog if str(p).strip()) + "\n\n"
    if res.get("ok"):
        parts = [
            f"Dev run completed (`{rid}`).",
            f"Iterations: {res.get('iterations')}, tests passed: {res.get('tests_passed')}, adapter: {res.get('adapter_used')}.",
        ]
        if res.get("pr_ready"):
            parts.append("PR-ready signal is true — review Mission Control for details.")
        return head + " ".join(parts)
    err = res.get("error") or res.get("status") or "failed"
    tail = json.dumps(res.get("steps") or [], default=str)[:1200]
    return head + f"Dev run did not complete cleanly (`{rid}`): {err}. Steps (truncated): {tail}"


def try_scheduled_dev_mission(
    gctx: GatewayContext,
    _text: str,
    db: Session,
) -> dict[str, Any] | None:
    """
    Scheduler-only path: :attr:`~app.services.gateway.context.GatewayContext.extras` carries
    ``scheduled_dev_mission`` JSON payload so dev execution stays inside :meth:`NexaGateway.handle_message`.
    """
    payload = gctx.extras.get("scheduled_dev_mission")
    if not isinstance(payload, dict):
        return None
    uid = (gctx.user_id or "").strip()
    wid = str(payload.get("workspace_id") or "").strip()
    if not uid or not wid:
        return None

    from app.services.events.unified_event import emit_unified_event
    from app.services.scheduler.dev_jobs import DEFAULT_GOALS
    from app.services.tasks.unified_task import NexaTask

    kind = str(payload.get("type") or "dev_mission")
    goal = str(payload.get("goal") or "").strip() or DEFAULT_GOALS.get(kind, "Scheduled dev mission")
    max_it = payload.get("max_iterations")
    if max_it is None:
        max_it = 3 if "fix" in kind else 1
    pref = payload.get("preferred_agent") or "local_stub"
    allow_write = bool(payload.get("allow_write", False))
    jid = gctx.extras.get("scheduler_job_id")
    task = NexaTask.from_scheduler_dev_payload(payload, job_id=str(jid) if jid else None)
    emit_unified_event(
        "task.dev.scheduled_start",
        task_id=task.id,
        user_id=uid,
        payload={"workspace_id": wid, "channel": gctx.channel},
    )
    res = run_dev_mission(
        db,
        uid,
        wid,
        goal,
        auto_pr=False,
        preferred_agent=str(pref),
        allow_write=allow_write,
        allow_commit=False,
        allow_push=False,
        cost_budget_usd=0.0,
        max_iterations=int(max_it),
        schedule=None,
        from_scheduler=True,
    )
    emit_unified_event(
        "task.dev.scheduled_done",
        task_id=task.id,
        user_id=uid,
        payload={"ok": bool(res.get("ok")), "run_id": str(res.get("run_id") or "")},
    )
    return {
        "mode": "chat",
        "text": format_dev_run_summary(res),
        "dev_run": res,
    }


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
                "Add a goal after `run dev:` — for example: `run dev: fix failing tests`. "
                "Register or pick a dev workspace in Mission Control first if you have not already."
            ),
        }

    rows = list_workspaces(db, user_id)
    if not rows:
        return {
            "mode": "chat",
            "text": (
                "No dev workspaces yet. Add or select a repo in Mission Control under Dev workspace, "
                "then say `run dev: …` with your goal."
            ),
        }

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
        }

    wid = rows[0].id
    res = run_dev_mission(db, user_id, wid, goal_field)
    return {
        "mode": "chat",
        "text": format_dev_run_summary(res),
        "dev_run": res,
    }


__all__ = ["format_dev_run_summary", "handle_run_dev_gateway", "parse_run_dev_goal", "try_scheduled_dev_mission"]
