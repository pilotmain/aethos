from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class AgentJob(Base, TimestampMixin):
    __tablename__ = "agent_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="telegram", nullable=False)
    kind: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    worker_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, default="", nullable=False)
    command_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True, nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    cursor_task_path: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    branch_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when the job is created from Telegram; used for dev-job completion push notifications.
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # e.g. .agent_tasks/dev_job_12.review.md when a written review file exists
    result_file: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default=None
    )  # normal | high | blocked
    tests_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default=None
    )  # not_run | passed | failed | skipped
    tests_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    # User explicitly allowed commit path after test failure (Telegram phrase)
    override_failed_tests: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # Worker lock (one active processor per job)
    locked_by: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    lock_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, index=True
    )
    failure_stage: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    failure_artifact_dir: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    artifact_dir: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # Whose Telegram approval opened commit (same format as user_id) — commit guard
    approved_by_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
