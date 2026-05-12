# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""REST payloads for user-defined custom agents (Phase 20)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CustomAgentSummary(BaseModel):
    handle: str = Field(description="Normalized agent_key")
    display_name: str
    description: str = ""
    safety_level: str = "standard"
    enabled: bool = True


class CustomAgentDetail(CustomAgentSummary):
    instructions_preview: str = Field(
        default="",
        description="Truncated system_prompt prefix for inspection.",
    )


class CustomAgentsListOut(BaseModel):
    agents: list[CustomAgentSummary]


class CustomAgentCreateIn(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=12000)


class CustomAgentCreateOut(BaseModel):
    ok: bool = True
    agent: CustomAgentSummary | None = None
    message: str = ""


class CustomAgentPatchIn(BaseModel):
    description: str | None = Field(None, max_length=20_000)
    instructions_append: str | None = Field(None, max_length=16_000)
    enabled: bool | None = None
