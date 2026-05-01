from pathlib import Path

from app.core.db import SessionLocal, ensure_schema
from app.schemas.agent_job import AgentJobCreate
from app.services.agent_job_service import AgentJobService
from app.services.handoff_tracking_service import HandoffTrackingService


def test_local_tool_handoff_marker_completes_job(tmp_path: Path) -> None:
    ensure_schema()
    db = SessionLocal()
    jobs = AgentJobService()
    tracker = HandoffTrackingService()
    try:
        marker = tmp_path / "cursor_task.done.md"
        job = jobs.create_job(
            db,
            "handoff_local_user",
            AgentJobCreate(
                kind="local_action",
                worker_type="local_tool",
                title="Cursor task",
                instruction="Do a small fix.",
                command_type="create-cursor-task",
                source="test",
                payload_json={"handoff_marker_path": str(marker)},
            ),
        )
        jobs.mark_waiting_for_cursor(db, job, str(tmp_path / "cursor_task.md"))
        marker.write_text("Finished the requested task.", encoding="utf-8")

        rows = tracker.process_waiting_handoffs(db)
        updated = jobs.get_job(db, "handoff_local_user", job.id)

        assert len(rows) == 1
        assert updated.status == "completed"
        assert "Finished the requested task." in (updated.result or "")
    finally:
        db.close()


def test_dev_handoff_marker_sets_ready_for_review(tmp_path: Path) -> None:
    ensure_schema()
    db = SessionLocal()
    jobs = AgentJobService()
    tracker = HandoffTrackingService()
    try:
        marker = tmp_path / "dev_job.done.md"
        job = jobs.create_job(
            db,
            "handoff_dev_user",
            AgentJobCreate(
                kind="dev_task",
                worker_type="dev_executor",
                title="Improve planner",
                instruction="Make planner smarter.",
                source="test",
                payload_json={"handoff_marker_path": str(marker)},
                approval_required=False,
            ),
        )
        jobs.repo.update(db, job, status="waiting_for_cursor", cursor_task_path=str(tmp_path / "dev_job.md"))
        marker.write_text("Implemented the requested planner changes.", encoding="utf-8")

        rows = tracker.process_waiting_handoffs(db)
        updated = jobs.get_job(db, "handoff_dev_user", job.id)

        assert len(rows) == 1
        assert updated.status == "ready_for_review"
        assert "planner changes" in (updated.result or "")
    finally:
        db.close()


def test_dev_handoff_without_payload_marker_uses_cursor_path(tmp_path: Path) -> None:
    """Regression: some rows lack handoff_marker_path; derive .done.md from cursor_task_path."""
    ensure_schema()
    db = SessionLocal()
    jobs = AgentJobService()
    tracker = HandoffTrackingService()
    try:
        job = jobs.create_job(
            db,
            "handoff_derive_user",
            AgentJobCreate(
                kind="dev_task",
                worker_type="dev_executor",
                title="Feature",
                instruction="Add a feature",
                source="test",
                payload_json={},
                approval_required=False,
            ),
        )
        prompt = tmp_path / f"dev_job_{job.id}.md"
        done = tmp_path / f"dev_job_{job.id}.done.md"
        jobs.repo.update(
            db,
            job,
            status="waiting_for_cursor",
            cursor_task_path=str(prompt),
            payload_json={},
        )
        done.write_text("Feature implemented.", encoding="utf-8")

        rows = tracker.process_waiting_handoffs(db)
        updated = jobs.get_job(db, "handoff_derive_user", job.id)

        assert len(rows) == 1
        assert updated.status == "ready_for_review"
        assert "Feature implemented." in (updated.result or "")
    finally:
        db.close()
