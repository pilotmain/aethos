from __future__ import annotations

import logging
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.agent_job_repo import AgentJobRepository
from app.schemas.agent_job import AgentJobCreate

HIGH_RISK_LOCAL_COMMANDS = frozenset(
    {"prepare-fix", "create-idea-repo", "dev-workspace-scaffold"}
)
TERMINAL_JOB_STATUSES = frozenset({"completed", "failed", "cancelled", "rejected", "blocked"})
_LOG = logging.getLogger(__name__)
NOTIFIABLE_JOB_STATUSES = frozenset(
    {
        "waiting_for_cursor",
        "agent_running",
        "changes_ready",
        "waiting_approval",
        "ready_for_review",
        "needs_commit_approval",
        "approved_to_commit",
        "completed",
        "failed",
        "cancelled",
        "rejected",
        "blocked",
        "needs_risk_approval",
    }
)


class AgentJobService:
    def __init__(self) -> None:
        self.repo = AgentJobRepository()

    def _log_chain_job_approved_if_applicable(self, job) -> None:
        """Observability: time from job creation to approval for chain host-executor jobs."""
        if (job.status or "") != "needs_approval":
            return
        if (job.worker_type or "") != "local_tool":
            return
        if (job.command_type or "").lower() != "host-executor":
            return
        pl = dict(job.payload_json or {})
        if (pl.get("host_action") or "").strip().lower() != "chain":
            return
        actions_in = pl.get("actions")
        n = len(actions_in) if isinstance(actions_in, list) else 0
        created = job.created_at
        if created:
            now = datetime.utcnow()
            approval_ms = (now - created).total_seconds() * 1000.0
        else:
            approval_ms = None
        _LOG.info(
            "Chain job approved id=%s steps=%s approval_time_ms=%s",
            job.id,
            n,
            f"{approval_ms:.2f}" if approval_ms is not None else "n/a",
            extra={
                "nexa_event": "chain_job_approved",
                "job_id": job.id,
                "chain_length": n,
                "approval_time_ms": round(approval_ms, 2) if approval_ms is not None else None,
            },
        )

    def create_dev_task_with_policy(
        self, db: Session, user_id: str, payload: AgentJobCreate, policy_text: str
    ) -> tuple:
        """Create dev_executor job with static policy gate; returns (job, policy_dict)."""
        from app.services.audit_service import audit
        from app.services.dev_agent_policy import evaluate_dev_job_policy

        pol = evaluate_dev_job_policy(policy_text)
        approval_required = (
            self._approval_required(payload.kind, payload.command_type)
            if payload.approval_required is None
            else payload.approval_required
        )
        pjson = dict(payload.payload_json or {})

        if not pol["allowed"]:
            job = self.repo.create(
                db,
                user_id=user_id,
                source=payload.source,
                kind=payload.kind,
                worker_type=payload.worker_type,
                title=payload.title,
                instruction=payload.instruction,
                command_type=payload.command_type,
                status="blocked",
                approval_required=approval_required,
                payload_json={**pjson, "policy": pol},
                telegram_chat_id=payload.telegram_chat_id or None,
                error_message=(pol.get("reason") or "Blocked by policy")[:2000],
                risk_level="blocked",
            )
            audit(
                db,
                event_type="job.blocked_by_policy",
                actor="bot",
                user_id=user_id,
                job_id=job.id,
                message=(pol.get("reason") or "")[:2000],
                metadata={"policy": pol},
            )
            return job, pol

        if pol.get("requires_extra_approval"):
            job = self.repo.create(
                db,
                user_id=user_id,
                source=payload.source,
                kind=payload.kind,
                worker_type=payload.worker_type,
                title=payload.title,
                instruction=payload.instruction,
                command_type=payload.command_type,
                status="needs_risk_approval",
                approval_required=True,
                payload_json={**pjson, "policy": pol},
                telegram_chat_id=payload.telegram_chat_id or None,
                risk_level="high",
            )
            audit(
                db,
                event_type="job.created",
                actor="bot",
                user_id=user_id,
                job_id=job.id,
                message=f"Dev job #{job.id} needs high-risk approval",
                metadata={"policy": pol},
            )
            return job, pol

        job = self.create_job(db, user_id, payload)
        pl = dict(job.payload_json or {})
        pl["policy"] = pol
        job = self.repo.update(db, job, payload_json=pl, risk_level=pol.get("risk", "normal"))
        audit(
            db,
            event_type="job.created",
            actor="bot",
            user_id=user_id,
            job_id=job.id,
            message=f"Dev job #{job.id} created (policy: {pol.get('risk', 'normal')})",
            metadata={"policy": pol},
        )
        return job, pol

    def approve_high_risk(self, db: Session, user_id: str, job_id: int):
        """needs_risk_approval -> needs_approval (user acknowledged high-risk)."""
        job = self.get_job(db, user_id, job_id)
        if (job.status or "") != "needs_risk_approval":
            return job
        from app.services.audit_service import audit

        j = self.repo.update(
            db,
            job,
            status="needs_approval",
            error_message=None,
            payload_json={**dict(job.payload_json or {}), "high_risk_ack": True},
        )
        audit(
            db,
            event_type="job.approved_for_agent",
            actor="user",
            user_id=user_id,
            job_id=j.id,
            message="User acknowledged high-risk; awaiting approve job",
        )
        return j

    def create_job(self, db: Session, user_id: str, payload: AgentJobCreate):
        approval_required = (
            self._approval_required(payload.kind, payload.command_type)
            if payload.approval_required is None
            else payload.approval_required
        )
        initial_status = "needs_approval" if approval_required else "queued"
        return self.repo.create(
            db,
            user_id=user_id,
            source=payload.source,
            kind=payload.kind,
            worker_type=payload.worker_type,
            title=payload.title,
            instruction=payload.instruction,
            command_type=payload.command_type,
            status=initial_status,
            approval_required=approval_required,
            payload_json=payload.payload_json or {},
            telegram_chat_id=(payload.telegram_chat_id or None),
        )

    def list_jobs(self, db: Session, user_id: str, limit: int = 20):
        return self.repo.list_for_user(db, user_id, limit=limit)

    def get_job(self, db: Session, user_id: str, job_id: int):
        job = self.repo.get(db, job_id, user_id=user_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return job

    def get_latest_actionable(self, db: Session, user_id: str):
        return self.repo.get_latest_actionable(db, user_id)

    def get_latest(self, db: Session, user_id: str):
        jobs = self.repo.list_for_user(db, user_id, limit=1)
        return jobs[0] if jobs else None

    def get_latest_waiting_autonomous_approval(
        self, db: Session, user_id: str
    ) -> "AgentJob | None":
        """Most recent dev job in `waiting_approval` (Aider loop)."""
        j = self.repo.get_latest_by_statuses_for_user(
            db, user_id, ["waiting_approval"]
        )
        if not j or (j.worker_type or "") != "dev_executor":
            return None
        return j

    def mark_autonomous_approved(
        self, db: Session, user_id: str, *, job_id: int | None = None
    ) -> "AgentJob | None":
        """`waiting_approval` -> `approved_to_commit` (user typed `approve` or button)."""
        from app.services.audit_service import audit

        if job_id is not None:
            j = self.get_job(db, user_id, job_id)
            if (j.status or "") != "waiting_approval" or (j.worker_type or "") != "dev_executor":
                return None
        else:
            j = self.get_latest_waiting_autonomous_approval(db, user_id)
        if not j:
            return None
        if (j.tests_status or "") == "failed" and not (getattr(j, "override_failed_tests", False) or False):
            return None
        out = self.repo.update(
            db, j, status="approved_to_commit", error_message=None, approved_by_user_id=user_id
        )
        audit(
            db,
            event_type="job.approved_to_commit",
            actor="user",
            user_id=user_id,
            job_id=out.id,
            message="User approved commit (Telegram)",
        )
        return out

    def mark_autonomous_rejected(
        self, db: Session, user_id: str, *, job_id: int | None = None
    ) -> "AgentJob | None":
        """`waiting_approval` -> `reverted` (git) + `rejected` status."""
        from app.services.aider_autonomous_loop import revert_aider_changes_on_branch
        from app.services.audit_service import audit

        if job_id is not None:
            j = self.get_job(db, user_id, job_id)
            if (j.status or "") != "waiting_approval" or (j.worker_type or "") != "dev_executor":
                return None
        else:
            j = self.get_latest_waiting_autonomous_approval(db, user_id)
        if not j:
            return None
        ok, note = revert_aider_changes_on_branch(j)
        base = (j.result or "")[:3000] if (j.result or "") else ""
        rtxt = f"Rejected. {note}" + (f"\n\nPrior summary:\n{base}" if base else "")
        if not ok:
            rtxt = f"Reject recorded; revert may have failed: {note}\n\n{rtxt[:2000]}"
        out = self.repo.update(
            db,
            j,
            status="rejected",
            completed_at=datetime.utcnow(),
            result=rtxt[:10_000],
            error_message=None if ok else (note or "")[:2000],
        )
        audit(
            db,
            event_type="job.reverted",
            actor="user",
            user_id=user_id,
            job_id=j.id,
            message=note[:2000] if note else "revert",
        )
        audit(
            db,
            event_type="job.rejected",
            actor="user",
            user_id=user_id,
            job_id=out.id,
            message="User rejected changes",
        )
        return out

    def decide(self, db: Session, user_id: str, job_id: int, decision: str):
        job = self.get_job(db, user_id, job_id)
        if job.status in TERMINAL_JOB_STATUSES:
            return job
        if (job.status or "") == "needs_risk_approval" and decision == "approve":
            return job
        if decision == "approve":
            self._log_chain_job_approved_if_applicable(job)
            return self.repo.update(
                db,
                job,
                status="approved",
                approved_at=datetime.utcnow(),
                error_message=None,
            )
        return self.repo.update(
            db,
            job,
            status="cancelled",
            completed_at=datetime.utcnow(),
            result="Denied by user.",
            error_message=None,
        )

    def cancel(self, db: Session, user_id: str, job_id: int):
        job = self.get_job(db, user_id, job_id)
        if job.status in TERMINAL_JOB_STATUSES:
            return job
        return self.repo.update(
            db,
            job,
            status="cancelled",
            completed_at=datetime.utcnow(),
            result="Cancelled by user.",
            error_message=None,
        )

    def approve_review(self, db: Session, user_id: str, job_id: int):
        job = self.get_job(db, user_id, job_id)
        if job.status != "ready_for_review":
            return job
        return self.repo.update(
            db,
            job,
            status="review_approved",
            result=(job.result or "") + "\n\nReview approved by user.",
            error_message=None,
        )

    def approve_commit(self, db: Session, user_id: str, job_id: int):
        job = self.get_job(db, user_id, job_id)
        if job.status != "needs_commit_approval":
            return job
        return self.repo.update(
            db,
            job,
            status="commit_approved",
            result=(job.result or "") + "\n\nCommit approved by user.",
            error_message=None,
        )

    def mark_needs_commit_approval(self, db: Session, job, result: str):
        return self.repo.update(
            db,
            job,
            status="needs_commit_approval",
            result=result,
            error_message=None,
        )

    def jobs_needing_notification(self, db: Session) -> list:
        rows = self.repo.list_recent(db, limit=120)
        out = []
        for job in rows:
            if job.status not in NOTIFIABLE_JOB_STATUSES:
                continue
            payload = dict(job.payload_json or {})
            if payload.get("last_notified_status") == job.status:
                continue
            out.append(job)
        return out

    def mark_notified(self, db: Session, job):
        payload = dict(job.payload_json or {})
        payload["last_notified_status"] = job.status
        self.repo.update(db, job, payload_json=payload)

    def mark_waiting_for_cursor(self, db: Session, job, task_path: str):
        return self.repo.update(db, job, status="waiting_for_cursor", cursor_task_path=task_path)

    def mark_completed(self, db: Session, job, result: str, **extra):
        return self.repo.update(
            db,
            job,
            status="completed",
            completed_at=datetime.utcnow(),
            result=result,
            error_message=None,
            **extra,
        )

    def mark_failed(
        self, db: Session, job, error_message: str, **extra: object
    ) -> "AgentJob":
        """Mark job failed. `extra` may set result, tests_status, tests_output, etc."""
        return self.repo.update(
            db,
            job,
            status="failed",
            completed_at=datetime.utcnow(),
            error_message=(error_message or "")[:4000] or "Unknown error",
            **extra,
        )

    def set_changes_requested(self, db: Session, user_id: str, job_id: int) -> "AgentJob | None":
        """waiting_approval -> changes_requested (awaiting free-text revision on phone)."""
        from app.services.audit_service import audit

        j = self.get_job(db, user_id, job_id)
        if (j.worker_type or "") != "dev_executor":
            return None
        if (j.status or "") != "waiting_approval":
            return None
        out = self.repo.update(
            db,
            j,
            status="changes_requested",
            error_message=None,
        )
        audit(
            db,
            event_type="job.changes_requested",
            actor="user",
            user_id=user_id,
            job_id=out.id,
            message="User asked for changes via button",
        )
        return out

    def apply_revision_and_requeue(
        self, db: Session, user_id: str, job_id: int, revision_instruction: str
    ) -> "AgentJob | None":
        from app.services.aider_autonomous_loop import write_revision_task_file

        j = self.get_job(db, user_id, job_id)
        if (j.worker_type or "") != "dev_executor":
            return None
        if (j.status or "") != "changes_requested":
            return None
        if not (revision_instruction or "").strip():
            return None
        pl = dict(j.payload_json or {})
        n = int(pl.get("revision_count", 0) or 0) + 1
        pl["revision_count"] = n
        write_revision_task_file(j, (revision_instruction or "").strip(), n)
        from app.services.audit_service import audit

        out = self.repo.update(
            db,
            j,
            status="approved",
            error_message=None,
            completed_at=None,
            override_failed_tests=False,
            payload_json=pl,
        )
        audit(
            db,
            event_type="job.requeued_for_revision",
            actor="user",
            user_id=user_id,
            job_id=out.id,
            message=f"Revision #{n} written; worker will run on same branch",
        )
        return out

    def mark_waiting_approval_despite_failed_tests(
        self, db: Session, user_id: str, job_id: int
    ) -> "AgentJob | None":
        from app.services.audit_service import audit

        j = self.get_job(db, user_id, job_id)
        if (j.worker_type or "") != "dev_executor":
            return None
        if (j.status or "") != "failed" or (j.tests_status or "") != "failed":
            return None
        base = (j.result or j.error_message or "Tests failed.").strip()[:10_000]
        out = self.repo.update(
            db,
            j,
            status="waiting_approval",
            error_message=None,
            override_failed_tests=True,
            result=(base or "Tests failed — review the branch and diff before approving.")[:12_000],
            completed_at=None,
        )
        audit(
            db,
            event_type="job.waiting_approval",
            actor="user",
            user_id=user_id,
            job_id=out.id,
            message="User approved review despite failed tests (explicit phrase)",
        )
        from app.services.gateway.approval_persistence import persist_job_waiting_approval

        persist_job_waiting_approval(
            db,
            out,
            ctx=None,
            resume_kind="host_worker_poll",
            original_action="override_failed_tests",
            risk="failed_tests_override",
        )
        return out

    def retry_dev_job(self, db: Session, user_id: str, job_id: int) -> "AgentJob | None":
        from app.services.audit_service import audit

        j = self.get_job(db, user_id, job_id)
        if (j.status or "") not in ("failed", "blocked", "changes_requested"):
            return None
        if (j.worker_type or "") != "dev_executor":
            return None
        self.repo.release_job_lock(db, j)
        pl = dict(j.payload_json or {})
        pl["reliability_retry_count"] = int(pl.get("reliability_retry_count", 0) or 0) + 1
        out = self.repo.update(
            db,
            j,
            status="approved",
            error_message=None,
            completed_at=None,
            override_failed_tests=False,
            failure_stage=None,
            failure_artifact_dir=None,
            payload_json=pl,
        )
        audit(
            db,
            event_type="job.retried",
            actor="user",
            user_id=user_id,
            job_id=out.id,
            message="User requested retry; job re-queued (approved); lock released",
        )
        return out

    def sweep_stale_dev_locks(self, db: Session) -> int:
        from datetime import datetime

        from sqlalchemy import select

        from app.models.agent_job import AgentJob
        from app.services.audit_service import audit

        now = datetime.utcnow()
        stmt = select(AgentJob).where(
            AgentJob.worker_type == "dev_executor",
            AgentJob.status.in_(["in_progress", "agent_running", "changes_ready"]),
            AgentJob.lock_expires_at.isnot(None),
            AgentJob.lock_expires_at < now,
        )
        n = 0
        for row in list(db.scalars(stmt).all()):
            self.mark_failed(
                db,
                row,
                (
                    f"Worker lock expired. Job may have been interrupted. Retry or cancel job #{row.id} "
                    "from chat or the web app."
                ),
                failure_stage="stale_lock",
            )
            audit(
                db,
                event_type="job.failed",
                actor="system",
                user_id=row.user_id,
                job_id=row.id,
                message="Stale dev lock",
            )
            n += 1
        return n

    def _approval_required(self, kind: str, command_type: str | None) -> bool:
        if kind == "dev_task":
            return True
        if kind == "ops_action":
            return True
        if kind == "local_action" and command_type in HIGH_RISK_LOCAL_COMMANDS:
            return True
        # Approval-gated host tools (never free-run shell from chat)
        if kind == "local_action" and (command_type or "").lower() == "host-executor":
            return True
        return False
