"""Lightweight SDK-shaped types for agents and integrations (Phase 54 MVP)."""

from __future__ import annotations

from typing import Any, TypedDict


class TaskEventDict(TypedDict, total=False):
    task_id: str
    type: str
    payload: dict[str, Any]
    ts: str


class SkillRefDict(TypedDict, total=False):
    id: str
    version: str
    permissions: list[str]


class ProviderRefDict(TypedDict, total=False):
    provider: str
    model: str
    purpose: str


__all__ = ["ProviderRefDict", "SkillRefDict", "TaskEventDict"]
