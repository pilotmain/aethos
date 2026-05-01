from datetime import datetime

from pydantic import BaseModel, Field


class AgentJobCreate(BaseModel):
    kind: str
    worker_type: str
    title: str = Field(min_length=1, max_length=255)
    instruction: str = Field(default="", max_length=12000)
    command_type: str | None = None
    payload_json: dict = Field(default_factory=dict)
    approval_required: bool | None = None
    source: str = "api"
    # When the job is created from Telegram, set for optional completion notifications.
    telegram_chat_id: str | None = None


class AgentJobApprovalRequest(BaseModel):
    decision: str = Field(pattern="^(approve|deny)$")


class AgentJobRead(BaseModel):
    id: int
    user_id: str
    source: str
    kind: str
    worker_type: str
    title: str
    instruction: str
    command_type: str | None
    status: str
    approval_required: bool
    approved_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    cursor_task_path: str | None
    branch_name: str | None
    commit_sha: str | None
    pr_url: str | None
    payload_json: dict
    result: str | None
    error_message: str | None
    telegram_chat_id: str | None
    result_file: str | None
    risk_level: str | None
    tests_status: str | None
    tests_output: str | None
    override_failed_tests: bool
    locked_by: str | None
    locked_at: datetime | None
    lock_expires_at: datetime | None
    failure_stage: str | None
    failure_artifact_dir: str | None
    artifact_dir: str | None
    approved_by_user_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
