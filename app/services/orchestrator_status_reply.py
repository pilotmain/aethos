"""Deterministic Mission Control summary for orchestrator-style questions."""

from __future__ import annotations

from sqlalchemy.orm import Session


def format_orchestrator_mc_snapshot(db: Session, user_id: str) -> str:
    """Summarize recent missions, tasks, and dev runs from :func:`build_execution_snapshot`."""
    from app.services.mission_control.nexa_next_state import build_execution_snapshot

    uid = (user_id or "").strip()
    if not uid:
        return "Sign in (Mission Control) so I can attach missions and dev runs to your account."

    snap = build_execution_snapshot(db, user_id=uid)
    missions = list(snap.get("missions") or [])[:8]
    tasks = list(snap.get("tasks") or [])[:8]
    dev_runs = list(snap.get("dev_runs") or [])[:6]

    lines: list[str] = ["### Mission Control snapshot", ""]
    if not missions and not tasks and not dev_runs:
        lines.append(
            "No missions, tasks, or dev runs showed up in the recent window for your account."
        )
    else:
        if missions:
            lines.append("**Missions**")
            for m in missions:
                title = str(m.get("title") or m.get("id") or "?")[:120]
                st = str(m.get("status") or "?")
                lines.append(f"- {title} — **{st}**")
            lines.append("")
        if tasks:
            lines.append("**Mission tasks**")
            for t in tasks:
                h = str(t.get("agent_handle") or "task")
                st = str(t.get("status") or "?")
                lines.append(f"- {h} — **{st}**")
            lines.append("")
        if dev_runs:
            lines.append("**Dev runs**")
            for r in dev_runs:
                g = (str(r.get("goal") or "")[:100] or "dev run").strip()
                st = str(r.get("status") or "?")
                lines.append(f"- {g} — **{st}**")

    lines.append("")
    lines.append(
        "_Reminder: chat-only replies do **not** prove a cloud deployment occurred unless there is "
        "a recorded tool run, dev mission output, or provider-side verification._"
    )
    return "\n".join(lines).strip()


__all__ = ["format_orchestrator_mc_snapshot"]
