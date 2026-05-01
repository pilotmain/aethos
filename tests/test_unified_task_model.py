"""Phase 43 — :class:`~app.services.tasks.unified_task.NexaTask` shape and conversions."""

from __future__ import annotations

from app.services.tasks.unified_task import NexaTask


def test_from_scheduler_dev_payload() -> None:
    payload = {"type": "dev_mission", "workspace_id": "wid-1", "goal": "ship fix"}
    t = NexaTask.from_scheduler_dev_payload(payload, job_id="job-abc")
    assert t.id == "job-abc"
    assert t.type == "scheduled"
    assert t.input == "ship fix"
    assert t.context["workspace_id"] == "wid-1"
    assert t.context["job_kind"] == "dev_mission"


def test_from_long_running_row() -> None:
    t = NexaTask.from_long_running_row(
        user_id="u1",
        session_key="sk",
        iteration=3,
        goal="keep going",
    )
    assert t.type == "system"
    assert "u1" in t.id and "sk" in t.id
    assert t.context["iteration"] == 3


def test_generates_id_without_job_id() -> None:
    p = {"type": "nightly_test", "workspace_id": "w", "goal": ""}
    a = NexaTask.from_scheduler_dev_payload(p)
    b = NexaTask.from_scheduler_dev_payload(p)
    assert len(a.id) >= 8
    assert a.id != b.id
