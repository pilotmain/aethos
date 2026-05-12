# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Pydantic models for governance API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OrganizationCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    id: str | None = Field(default=None, max_length=64, description="Optional explicit org id (e.g. org_test).")


class OrganizationOut(BaseModel):
    id: str
    name: str
    owner_user_id: str
    enabled: bool


class MemberCreateIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    role: str = Field(default="member", max_length=32)


class MemberPatchIn(BaseModel):
    role: str | None = Field(default=None, max_length=32)
    enabled: bool | None = None


class OrganizationPolicyPatchIn(BaseModel):
    """Merged into the ``default`` policy row's ``policy_json``."""

    policy_json: dict = Field(default_factory=dict)
