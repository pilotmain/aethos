"""Pydantic schemas for agent organization REST API."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
    assigned_to_handle: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="", max_length=20_000)
    priority: str = Field(default="normal", max_length=32)
    input_json: dict = Field(default_factory=dict)
    organization_id: int | None = None
