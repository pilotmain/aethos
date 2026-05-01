from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.agent_job_repo import AgentJobRepository
from app.services.agent_job_service import AgentJobService
from app.services.cursor_dev_handoff import fulfill_dev_job_after_done_file
from app.services.handoff_paths import resolve_handoff_marker_path


class HandoffTrackingService:
    def __init__(self) -> None:
        self.repo = AgentJobRepository()
        self.jobs = AgentJobService()

    def process_waiting_handoffs(self, db: Session) -> list:
        transitioned = []
        for job in self.repo.list_by_status(db, "waiting_for_cursor"):
            marker = resolve_handoff_marker_path(job)
            if not marker or not marker.is_file():
                continue
            if job.worker_type == "dev_executor":
                out = fulfill_dev_job_after_done_file(db, job)
                if out is not None:
                    transitioned.append(out)
            else:
                summary = marker.read_text(encoding="utf-8", errors="replace").strip()
                if len(summary) > 4000:
                    summary = summary[:4000] + "\n\n[TRUNCATED]"
                updated = self.jobs.mark_completed(
                    db,
                    job,
                    "Cursor reported the task is complete.\n\n"
                    + (summary or "No completion summary provided."),
                )
                transitioned.append(updated)
        return transitioned
