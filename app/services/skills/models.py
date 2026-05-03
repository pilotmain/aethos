"""Skill manifest schema (Phase 53)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

RiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class SkillMeta:
    id: str
    name: str
    description: str
    version: str
    author: str
    permissions: tuple[str, ...] = field(default_factory=tuple)
    entrypoint: str = "skill.py"
    privacy_policy: str = "firewall_required"
    risk_level: RiskLevel = "low"
    extra: dict[str, Any] = field(default_factory=dict)
