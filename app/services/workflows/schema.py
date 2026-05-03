"""YAML workflow schema (Phase 54 MVP)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowStep:
    id: str
    type: str
    depends_on: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowDefinition:
    name: str
    steps: list[WorkflowStep]


__all__ = ["WorkflowDefinition", "WorkflowStep"]
