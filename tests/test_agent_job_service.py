# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.core.db import SessionLocal, ensure_schema
from app.schemas.agent_job import AgentJobCreate
from app.services.agent_job_service import AgentJobService


def test_dev_executor_approved_picked_by_worker_type_not_kind() -> None:
    """Host executor queues by worker_type=dev_executor; kind is dev_task."""
    ensure_schema()
    db = SessionLocal()
    service = AgentJobService()
    try:
        j = service.create_job(
            db,
            "wt_pick_user",
            AgentJobCreate(
                kind="dev_task",
                worker_type="dev_executor",
                title="T",
                instruction="I",
                source="test",
            ),
        )
        assert j.kind == "dev_task" and (j.worker_type or "") == "dev_executor"
        a = service.decide(db, "wt_pick_user", j.id, "approve")
        assert a.status == "approved"
        nxt = service.repo.get_next_for_worker_statuses(
            db, "dev_executor", ["approved"]
        )
        # Oldest approved in the (shared) DB is returned first — only assert type invariants.
        assert nxt is not None
        assert nxt.kind == "dev_task" and nxt.status == "approved" and nxt.worker_type == "dev_executor"
    finally:
        db.close()


def test_dev_job_requires_approval() -> None:
    ensure_schema()
    db = SessionLocal()
    service = AgentJobService()
    try:
        job = service.create_job(
            db,
            "job_test_user",
            AgentJobCreate(
                kind="dev_task",
                worker_type="dev_executor",
                title="Improve planner",
                instruction="Make the planner more adaptive.",
                source="test",
            ),
        )
        assert job.status == "needs_approval"
        assert job.approval_required is True
    finally:
        db.close()


def test_low_risk_local_job_runs_without_approval() -> None:
    ensure_schema()
    db = SessionLocal()
    service = AgentJobService()
    try:
        job = service.create_job(
            db,
            "job_test_user_2",
            AgentJobCreate(
                kind="local_action",
                worker_type="local_tool",
                title="run-tests",
                instruction="",
                command_type="run-tests",
                source="test",
            ),
        )
        assert job.status == "queued"
        assert job.approval_required is False
    finally:
        db.close()


def test_host_executor_job_needs_approval() -> None:
    """host-executor uses allowlisted tools only; user must approve before local_tool_worker runs."""
    ensure_schema()
    db = SessionLocal()
    service = AgentJobService()
    try:
        job = service.create_job(
            db,
            "host_exec_user",
            AgentJobCreate(
                kind="local_action",
                worker_type="local_tool",
                title="git status",
                instruction="show repo status",
                command_type="host-executor",
                payload_json={"host_action": "git_status"},
                source="test",
            ),
        )
        assert job.status == "needs_approval"
        approved = service.decide(db, "host_exec_user", job.id, "approve")
        assert approved.status == "approved"
    finally:
        db.close()


def test_high_risk_local_job_needs_approval() -> None:
    ensure_schema()
    db = SessionLocal()
    service = AgentJobService()
    try:
        job = service.create_job(
            db,
            "job_test_user_3",
            AgentJobCreate(
                kind="local_action",
                worker_type="local_tool",
                title="prepare-fix",
                instruction="Patch the executor flow.",
                command_type="prepare-fix",
                source="test",
            ),
        )
        assert job.status == "needs_approval"
        approved = service.decide(db, "job_test_user_3", job.id, "approve")
        assert approved.status == "approved"
    finally:
        db.close()


def test_dev_review_and_commit_approvals() -> None:
    ensure_schema()
    db = SessionLocal()
    service = AgentJobService()
    try:
        job = service.create_job(
            db,
            "job_test_user_4",
            AgentJobCreate(
                kind="dev_task",
                worker_type="dev_executor",
                title="Improve review flow",
                instruction="Validate and summarize before commit.",
                source="test",
            ),
        )
        service.repo.update(db, job, status="ready_for_review")
        reviewed = service.approve_review(db, "job_test_user_4", job.id)
        assert reviewed.status == "review_approved"

        needs_commit = service.mark_needs_commit_approval(db, reviewed, "Review summary here.")
        assert needs_commit.status == "needs_commit_approval"

        commit_ready = service.approve_commit(db, "job_test_user_4", job.id)
        assert commit_ready.status == "commit_approved"
    finally:
        db.close()
