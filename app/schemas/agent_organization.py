"""Pydantic schemas for agent organization REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.services.custom_agents import normalize_agent_key
from app.services.sub_agent_registry import AgentRegistry


class AgentOrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=8000)


class AgentOrganizationOut(BaseModel):
    id: int
    name: str
    description: str | None
    enabled: bool


class AgentRoleCreate(BaseModel):
    agent_handle: str = Field(..., min_length=1, max_length=64)
    role: str = Field(..., min_length=1, max_length=200)
    skills: list[str] = Field(default_factory=list)
    reports_to_handle: str | None = Field(None, max_length=64)
    responsibilities: list[str] = Field(default_factory=list)


class AgentAssignmentCreate(BaseModel):
    """Create Mission Control / SQL-backed assignments.

    Accepts legacy/alternate bodies (``task``, ``agent_id``) from integrations that do not
    send ``assigned_to_handle`` + ``title`` explicitly.
    """

    assigned_to_handle: str | None = Field(default=None, max_length=64)
    agent_handle: str | None = Field(default=None, max_length=64)
    agent_id: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=500)
    task: str | None = Field(default=None, max_length=20_000)
    description: str = Field(default="", max_length=20_000)
    priority: str = Field(default="normal", max_length=32)
    input_json: dict[str, Any] = Field(default_factory=dict)
    organization_id: int | None = None
    # Phase 67 — when None, fall back to NEXA_ASSIGNMENT_AUTO_DISPATCH_DEFAULT (default true).
    # When true, POST /agent-assignments runs dispatch_assignment immediately and merges its result
    # into the response (still subject to host-tools / approval gates inside dispatch_assignment).
    auto_dispatch: bool | None = None

    @model_validator(mode="after")
    def _coerce_assignment_targets(self) -> "AgentAssignmentCreate":
        raw_handle = (self.assigned_to_handle or self.agent_handle or "").strip()
        handle = normalize_agent_key(raw_handle) if raw_handle else ""
        if not handle:
            aid = (self.agent_id or "").strip()
            if aid:
                ag = AgentRegistry().get_agent(aid)
                if ag is not None and (ag.name or "").strip():
                    handle = normalize_agent_key(ag.name)
        if not handle:
            raise ValueError(
                "Provide assigned_to_handle or agent_handle, or agent_id matching an orchestration sub-agent"
            )
        title = (self.title or "").strip() or (self.task or "").strip() or "Assignment"
        desc = (self.description or "").strip()
        if not desc and (self.task or "").strip():
            desc = (self.task or "").strip()
        self.assigned_to_handle = handle
        self.title = title[:500]
        self.description = desc[:20_000]
        return self
