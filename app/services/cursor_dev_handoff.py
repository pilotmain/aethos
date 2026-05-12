# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Finalize dev_executor jobs when `.agent_tasks/dev_job_{id}.done.md` appears:
build a `.review.md`, move DB to ready_for_review, optional Telegram push.
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models.agent_job import AgentJob

from app.services.agent_job_service import AgentJobService
from app.services.handoff_paths import AGENT_TASKS_DIR, PROJECT_ROOT, resolve_handoff_marker_path
from app.services.telegram_outbound import send_telegram_message

logger = logging.getLogger(__name__)


def _handoff_flag(payload: dict, name: str) -> bool:
    return bool((payload or {}).get(name) is True)


def done_path_for_job(job) -> Path:
    p = resolve_handoff_marker_path(job)
    if p is not None:
        return p
    return AGENT_TASKS_DIR / f"dev_job_{job.id}.done.md"


def review_path_for_job(job_id: int) -> Path:
    return AGENT_TASKS_DIR / f"dev_job_{job_id}.review.md"


def _run_tests_capture() -> str:
    if (os.getenv("HANDOFF_RUN_TESTS", "true").strip().lower() not in {"1", "true", "yes", "on"}):
        return "Tests/checks skipped (HANDOFF_RUN_TESTS=false)."
    cmd = os.getenv("DEV_AGENT_TEST_COMMAND", "python -m compileall -q app")
    try:
        p = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            shell=True,
            text=True,
            capture_output=True,
            timeout=600,
        )
        out = (p.stdout or "") + (("\nSTDERR:\n" + p.stderr) if p.stderr else "")
        if p.returncode not in (0, 5):
            return f"Checks exit {p.returncode}:\n" + out[-8000:]
        return f"Checks finished (exit {p.returncode}):\n" + out[-8000:]
    except Exception as exc:  # noqa: BLE001
        return f"Test/check error: {exc!s}"[:4000]


def build_final_worker_review(job, cursor_result: str, test_output: str) -> str:
    try:
        diff_stat = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=str(PROJECT_ROOT),
            text=True,
            capture_output=True,
            timeout=60,
        ).stdout
    except OSError:
        diff_stat = ""
    try:
        changed = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(PROJECT_ROOT),
            text=True,
            capture_output=True,
            timeout=60,
        ).stdout
    except OSError:
        changed = ""
    cr = (cursor_result or "")[:12_000]
    if len(cursor_result or "") > 12_000:
        cr += "\n[TRUNCATED]"
    return (
        f"# Final worker review for job #{job.id}\n\n"
        f"## Job\n{job.title}\n\n"
        f"## Cursor / agent result (.done.md)\n{cr}\n\n"
        f"## Test / check output\n{(test_output or '')[:5000]}\n\n"
        f"## Changed files (git status — short)\n{changed or '[not a git worktree or no changes]'}\n\n"
        f"## Diff stat\n{diff_stat or '[no diff]'}\n"
    ).strip()


def fulfill_dev_job_after_done_file(db: Session, job: AgentJob) -> AgentJob | None:
    """
    If dev_executor + waiting_for_cursor and .done.md exists: write .review.md, set ready_for_review,
    optional Telegram. Idempotent if payload has handoff_fulfillment_done.
    """
    if (getattr(job, "worker_type", None) or "") != "dev_executor":
        return None
    if (job.status or "") != "waiting_for_cursor":
        return None
    if _handoff_flag(dict(job.payload_json or {}), "handoff_fulfillment_done"):
        return None

    done = done_path_for_job(job)
    if not done.is_file():
        return None

    raw = done.read_text(encoding="utf-8", errors="replace")
    if len(raw) > 100_000:
        raw = raw[:100_000] + "\n[TRUNCATED]"

    test_out = _run_tests_capture()
    final_text = build_final_worker_review(job, raw, test_out)
    AGENT_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    rpath = review_path_for_job(job.id)
    rpath.write_text(final_text, encoding="utf-8")

    jobs = AgentJobService()
    summary_for_db = f"Handoff complete — {rpath.name}\n\n" + final_text
    if len(summary_for_db) > 12_000:
        summary_for_db = summary_for_db[:12_000] + "…"

    pl = dict(job.payload_json or {})
    pl["handoff_fulfillment_done"] = True
    pl["handoff_marker_path"] = str(done)

    updated = jobs.repo.update(
        db,
        job,
        status="ready_for_review",
        result=summary_for_db,
        result_file=str(rpath),
        error_message=None,
        payload_json=pl,
    )

    chat = (getattr(updated, "telegram_chat_id", None) or "").strip() or str(
        (updated.payload_json or {}).get("telegram_chat_id") or ""
    )
    p2 = dict(updated.payload_json or {})
    if not _handoff_flag(p2, "completion_push_sent") and chat:
        preview = (final_text[:3500] + "…") if len(final_text) > 3500 else final_text
        if send_telegram_message(
            chat,
            f"Cursor / agent finished job #{updated.id}.\n\n{preview}",
        ):
            p2["completion_push_sent"] = True
            updated = jobs.repo.update(db, updated, payload_json=p2)
    return updated
