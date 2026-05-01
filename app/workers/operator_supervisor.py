from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.agent_job_service import AgentJobService
from app.services.audit_service import audit
from app.services.handoff_tracking_service import HandoffTrackingService
from app.services.nexa_safety_policy import policy_audit_metadata

PROJECT_ROOT = Path(__file__).resolve().parents[2]

logger = logging.getLogger(__name__)


def _run_script(script_path: str, extra_env: dict[str, str] | None = None) -> dict:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, script_path],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        env=env,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout[-3000:],
        "stderr": proc.stderr[-3000:],
    }


def _safe_auto_commit_allowed(job) -> bool:
    payload = dict(job.payload_json or {})
    if payload.get("safe_auto_commit") is True:
        return True
    title = (job.title or "").lower()
    return any(token in title for token in ("finish", "finalize", "wrap up", "report"))


def process_supervisor_cycle() -> dict:
    settings = get_settings()
    db: Session = SessionLocal()
    jobs = AgentJobService()
    result: dict[str, object] = {
        "local_tool": None,
        "dev_executor": None,
        "auto_approved_dev": [],
        "auto_reviewed": [],
        "auto_committed": [],
        "handoffs": [],
    }
    try:
        audit(
            db,
            event_type="safety.worker.invoke",
            actor="supervisor",
            message="operator_supervisor_cycle",
            metadata=policy_audit_metadata(),
        )
        if getattr(settings, "nexa_autonomous_mode", False):
            result["autonomous_mode"] = True
            from app.services.autonomy.planner import autonomous_planner

            result["autonomous_planner"] = autonomous_planner(db)
        if settings.operator_auto_approve_queued_dev_jobs:
            pending = jobs.repo.list_by_status(db, "needs_approval", worker_type="dev_executor")
            for job in pending:
                if (job.kind or "") != "dev_task":
                    continue
                try:
                    jobs.decide(db, job.user_id, job.id, "approve")
                    result["auto_approved_dev"].append(job.id)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("operator_auto_approve_queued_dev_jobs failed job_id=%s: %s", job.id, exc)

        if settings.operator_auto_approve_review:
            for job in jobs.repo.list_by_status(db, "ready_for_review", worker_type="dev_executor"):
                jobs.approve_review(db, job.user_id, job.id)
                result["auto_reviewed"].append(job.id)

        if settings.operator_auto_approve_all_commits:
            for job in jobs.repo.list_by_status(db, "needs_commit_approval", worker_type="dev_executor"):
                try:
                    jobs.approve_commit(db, job.user_id, job.id)
                    result["auto_committed"].append(job.id)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("operator_auto_approve_all_commits failed job_id=%s: %s", job.id, exc)
        elif settings.operator_auto_approve_commit_safe:
            for job in jobs.repo.list_by_status(db, "needs_commit_approval", worker_type="dev_executor"):
                if _safe_auto_commit_allowed(job):
                    jobs.approve_commit(db, job.user_id, job.id)
                    result["auto_committed"].append(job.id)

        if settings.operator_auto_run_local_tools:
            queued_local = jobs.repo.get_next_for_worker_statuses(db, "local_tool", ["queued", "approved"])
            if queued_local:
                result["local_tool"] = _run_script("scripts/local_tool_worker.py")

        # Host loop (./run_everything.sh + host_dev_executor) uses the same Postgres; do not also
        # run the script inside the API container when DEV_EXECUTOR_ON_HOST=1.
        run_dev_in_container = (
            settings.operator_auto_run_dev_executor
            and not settings.dev_executor_on_host
        )
        if run_dev_in_container and jobs.repo.has_dev_executor_runnable(db):
            result["dev_executor"] = _run_script("scripts/dev_agent_executor.py")

        # Same filesystem as dev executor; runs every OPERATOR_POLL_SECONDS (often faster than bot-only poll).
        handoff_svc = HandoffTrackingService()
        transitioned = handoff_svc.process_waiting_handoffs(db)
        result["handoffs"] = [j.id for j in transitioned]
        return result
    finally:
        db.close()
