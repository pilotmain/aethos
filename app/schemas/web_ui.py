# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.agent_job import AgentJobRead


class WebChatMessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=12_000)
    # Web UI chat session (ConversationContext.session_id); default legacy thread
    session_id: str | None = Field(default=None, max_length=64)


class WebResponseSourceItem(BaseModel):
    url: str
    title: str | None = None


class UsageSummaryOut(BaseModel):
    """No prompts or keys — aggregate for one request/turn (may span multiple model calls)."""

    used_llm: bool
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None
    provider: str | None = None
    model: str | None = None
    used_user_key: bool = False
    # When multiple provider/model calls share one request_id (e.g. intent + chat)
    mix_display: str | None = Field(default=None, max_length=420)
    # Human-readable; optional, client may ignore
    subline: str | None = None


class DecisionSummaryOut(BaseModel):
    """User-safe decision transparency (not chain-of-thought, no hidden prompts)."""

    agent: str
    action: str
    tool: str | None = None
    reason: str
    risk: str
    approval_required: bool = False
    intent: str | None = None


class SystemEventItemOut(BaseModel):
    """Small OS-style row for the Web client (not a user/assistant turn)."""

    kind: str = Field(default="", max_length=64)
    text: str = Field(default="", max_length=1_200)


class WebChatMessageOut(BaseModel):
    reply: str
    intent: str | None = None
    agent_key: str | None = None
    related_jobs: list[AgentJobRead] = Field(default_factory=list)
    response_kind: str | None = None
    permission_required: dict[str, Any] | None = Field(
        default=None,
        description="Structured inline permission card when host action awaits approval.",
    )
    sources: list[WebResponseSourceItem] = Field(default_factory=list)
    web_tool_line: str | None = None
    usage_summary: UsageSummaryOut | None = None
    request_id: str | None = None
    decision_summary: DecisionSummaryOut | None = None
    system_events: list[SystemEventItemOut] = Field(
        default_factory=list,
        description="Ephemeral work-system rows (tool/job/document lines).",
    )


class WebMessageItem(BaseModel):
    role: str
    content: str


class FlowSummaryItemOut(BaseModel):
    has_flow: bool
    expired: bool
    goal: str | None
    total_steps: int
    completed_steps: int
    next_command: str | None


class WebWorkContextOut(BaseModel):
    flow: FlowSummaryItemOut
    lines: list[str] = Field(default_factory=list, description="Human-readable current-work lines for the right panel")
    recent_artifacts: list[dict[str, Any]] = Field(default_factory=list)


class WebSessionOut(BaseModel):
    id: str
    title: str
    summary: str | None
    active_topic: str | None
    last_agent: str | None
    last_intent: str | None
    updated_at: datetime | None
    message_count: int
    # Short line for the sidebar (e.g. first user line or active topic)
    preview: str | None = None


class WebSessionCreateIn(BaseModel):
    title: str = Field(default="New chat", min_length=1, max_length=80)


class WebSessionCreatedOut(BaseModel):
    id: str
    title: str


class WebByokKeyIn(BaseModel):
    provider: str
    key: str = Field(min_length=1, max_length=4096)


class WebByokKeyRow(BaseModel):
    provider: str
    has_key: bool
    last4: str


class WebIndicatorItem(BaseModel):
    id: str
    label: str
    level: str
    detail: str | None = None


class WebHostExecutorPanelOut(BaseModel):
    """Safe host-executor snapshot for the System tab (no secrets, no new actions)."""

    enabled: bool
    work_root: str
    allowed_host_actions: list[str] = Field(default_factory=list)
    allowed_run_names: list[str] = Field(default_factory=list)
    timeout_seconds: int
    max_file_bytes: int


class WebSystemStatusOut(BaseModel):
    indicators: list[WebIndicatorItem] = Field(default_factory=list)
    host_executor: WebHostExecutorPanelOut | None = Field(
        default=None,
        description="Allowlisted host tools status (worker runs jobs after approval)",
    )


class WebReleaseNotesOut(BaseModel):
    """Latest dated release section; safe for a public, unauthenticated read."""

    release_id: str
    date: str
    title: str
    items: list[str] = Field(default_factory=list)
    full_text: str = Field(default="")


class WebReleaseLatestOut(BaseModel):
    """Authenticated latest release strip for web banner (compact JSON)."""

    release_id: str
    items: list[str] = Field(default_factory=list)
    full_text: str = Field(default="", description="Latest section markdown for optional inline expand")


class WebDocumentGenerateIn(BaseModel):
    title: str = Field(
        default="",
        max_length=500,
        description="Optional; when empty the server derives a title from the body and source type.",
    )
    format: str = Field(
        "pdf",
        description="One of: md, txt, docx, pdf",
    )
    body_markdown: str = Field(
        default="",
        max_length=500_000,
        description="Main body (markdown-friendly); may be empty if title carries enough context.",
    )
    source_type: str = Field(
        "chat",
        max_length=64,
    )
    source_ref: str | None = Field(
        default=None,
        max_length=256,
    )
    allow_sensitive: bool = False


class WebDocumentItemOut(BaseModel):
    id: int
    title: str
    format: str
    file_path: str
    source_type: str
    source_ref: str | None
    created_at: datetime
    download_url: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class WebDocumentGenerateOut(BaseModel):
    id: int
    title: str
    format: str
    download_url: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class WebAccessPermissionOut(BaseModel):
    id: int
    scope: str
    target: str
    risk_level: str
    status: str
    expires_at: datetime | None
    created_at: datetime | None
    last_used_at: datetime | None = None
    reason: str | None = None
    grant_mode: str = "persistent"

    model_config = {"from_attributes": True}


class WebAccessPermissionGrantIn(BaseModel):
    grant_mode: str | None = None
    grant_session_hours: float | None = None


class WebWorkspaceRootOut(BaseModel):
    id: int
    path_normalized: str
    label: str | None
    is_active: bool
    created_at: datetime | None

    model_config = {"from_attributes": True}


class WebWorkspaceRootCreateIn(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    label: str | None = Field(default=None, max_length=256)


class WebNexaWorkspaceProjectOut(BaseModel):
    id: int
    name: str
    path_normalized: str
    description: str | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class WebNexaWorkspaceProjectCreateIn(BaseModel):
    path: str = Field(min_length=1, max_length=2048)
    name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=4000)


class WebSessionActiveProjectIn(BaseModel):
    """Set active Nexa workspace project for a chat session."""

    project_id: int | None = None
    session_id: str = Field(default="default", max_length=64)


class WebActiveWorkspaceProjectResponse(BaseModel):
    ok: bool = True
    active_project_id: int | None = None
    project: WebNexaWorkspaceProjectOut | None = None
