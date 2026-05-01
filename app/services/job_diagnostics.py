"""Heuristics for dev jobs that look stuck or need attention."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.agent_job import AgentJob
from app.services.handoff_paths import AGENT_TASKS_DIR, PROJECT_ROOT
from app.services.memory_preferences import count_non_empty_preferences, get_memory_preferences_dict
from app.services.system_memory_files import memory_path

logger = logging.getLogger(__name__)


def task_prompt_path_for_job(job: AgentJob) -> Path:
    ctp = (getattr(job, "cursor_task_path", None) or "").strip()
    if ctp:
        p = Path(ctp)
        if p.is_absolute():
            return p
        return (PROJECT_ROOT / ctp).resolve()
    return AGENT_TASKS_DIR / f"dev_job_{job.id}.md"


def collect_job_diagnostics(
    db: Session,
    jobs: list[AgentJob],
) -> list[str]:
    """Actionable one-line issues for the doctor (no DB migration; uses existing status names)."""
    s = get_settings()
    out: list[str] = []
    if not jobs:
        return out

    dev = [j for j in jobs if (j.worker_type or "") == "dev_executor"]
    now = datetime.now()

    for j in dev:
        st = (j.status or "").strip()
        if st == "approved" and (j.approved_at or j.updated_at):
            ref = j.approved_at or j.updated_at or j.created_at
            if ref and (now - ref) > timedelta(minutes=5):
                out.append(
                    f"Job #{j.id} in `approved` for {int((now - ref).total_seconds() // 60)}+ min — check host worker, pause flag, or DB connectivity."
                )
        if st == "waiting_for_cursor":
            p = task_prompt_path_for_job(j)
            if not p.is_file():
                out.append(
                    f"Job #{j.id} is `waiting_for_cursor` but prompt file is missing: `{p}`."
                )
        if st == "agent_running":
            start = j.started_at or j.updated_at
            tmo = int(s.dev_agent_timeout_seconds or 1800)
            if start and (now - start) > timedelta(seconds=tmo):
                out.append(
                    f"Job #{j.id} in `agent_running` longer than dev timeout ({tmo}s) — the worker may be hung; check host logs."
                )
        if st == "needs_commit_approval" and (j.updated_at or j.created_at):
            u = j.updated_at or j.created_at
            if u and (now - u) > timedelta(hours=24):
                out.append(
                    f"Job #{j.id} is `needs_commit_approval` for 24+ hours — tap approve/reject in Telegram or retry."
                )

    failed = [j for j in dev if (j.status or "") == "failed"][:15]
    reasons = [((j.error_message or j.result or "") or "").strip()[:100] for j in failed if (j.error_message or j.result)]
    for text, c in Counter(reasons).most_common(3):
        if c >= 2 and text:
            out.append(f"Repeated failed jobs ({c}×): {text[:200]}")

    return out


def format_last_memory_line() -> str:
    try:
        p = memory_path()
        if not p.is_file():
            return "—"
        lines = [ln.strip() for ln in p.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
        if not lines:
            return "— (empty file)"
        return lines[-1][:200]
    except OSError as e:
        logger.debug("read memory tail: %s", e)
        return "— (unreadable)"


def durable_preferences_count() -> int:
    return count_non_empty_preferences(get_memory_preferences_dict())
