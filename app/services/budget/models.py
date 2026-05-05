"""
Budget and usage tracking models (Phase 28).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class UsageType(Enum):
    LLM_CALL = "llm_call"
    AGENT_TASK = "agent_task"
    CHAIN_ACTION = "chain_action"
    BROWSER_ACTION = "browser_action"
    SOCIAL_POST = "social_post"
    PR_REVIEW = "pr_review"


class BudgetStatus(Enum):
    ACTIVE = "active"
    WARNING = "warning"
    PAUSED = "paused"
    OVERRIDE = "override"


@dataclass
class MemberBudget:
    """Budget configuration for a team member (sub-agent)."""

    member_id: str
    monthly_limit: int = 1_000_000
    current_usage: int = 0
    status: BudgetStatus = BudgetStatus.ACTIVE
    warning_sent_80: bool = False
    warning_sent_95: bool = False
    reset_day: int = 1
    last_reset: date | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def remaining(self) -> int:
        return max(0, self.monthly_limit - self.current_usage)

    def usage_percentage(self) -> float:
        if self.monthly_limit <= 0:
            return 100.0
        return (self.current_usage / self.monthly_limit) * 100

    def should_warn_80(self) -> bool:
        return not self.warning_sent_80 and self.usage_percentage() >= 80

    def should_warn_95(self) -> bool:
        return not self.warning_sent_95 and self.usage_percentage() >= 95

    def is_exhausted(self) -> bool:
        return self.current_usage >= self.monthly_limit and self.monthly_limit > 0

    def can_execute(self, estimated_tokens: int = 0) -> bool:
        if self.status == BudgetStatus.OVERRIDE:
            return True
        if self.status == BudgetStatus.PAUSED:
            return False
        if self.monthly_limit <= 0:
            return False
        if self.is_exhausted():
            return False
        return self.current_usage + estimated_tokens <= self.monthly_limit

    def to_user_display(self) -> str:
        percentage = self.usage_percentage()
        if percentage >= 95:
            bar = "██████████"
        elif percentage >= 80:
            bar = "████████░░"
        elif percentage >= 60:
            bar = "██████░░░░"
        elif percentage >= 40:
            bar = "████░░░░░░"
        elif percentage >= 20:
            bar = "██░░░░░░░░"
        else:
            bar = "█░░░░░░░░░"
        status_emoji = {
            BudgetStatus.ACTIVE: "🟢",
            BudgetStatus.WARNING: "🟡",
            BudgetStatus.PAUSED: "🔴",
            BudgetStatus.OVERRIDE: "🔵",
        }.get(self.status, "⚪")
        return (
            f"{status_emoji} {bar} {self.current_usage:,} / {self.monthly_limit:,} "
            f"tokens ({percentage:.0f}%)"
        )


@dataclass
class UsageRecord:
    """Individual usage record for audit."""

    id: str
    member_id: str
    member_name: str | None = None
    usage_type: UsageType = UsageType.LLM_CALL
    tokens: int = 0
    estimated_cost_usd: float = 0.0
    description: str | None = None
    project_id: str | None = None
    task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        member_id: str,
        tokens: int,
        usage_type: UsageType = UsageType.LLM_CALL,
        description: str | None = None,
    ) -> UsageRecord:
        estimated_cost_usd = (tokens / 1000) * 0.002
        return cls(
            id=str(uuid.uuid4())[:8],
            member_id=member_id,
            usage_type=usage_type,
            tokens=tokens,
            estimated_cost_usd=estimated_cost_usd,
            description=description,
        )

    def to_user_display(self) -> str:
        type_emoji = {
            UsageType.LLM_CALL: "🤖",
            UsageType.AGENT_TASK: "👤",
            UsageType.CHAIN_ACTION: "⛓️",
            UsageType.BROWSER_ACTION: "🌐",
            UsageType.SOCIAL_POST: "📱",
            UsageType.PR_REVIEW: "📝",
        }.get(self.usage_type, "⚪")
        return (
            f"{type_emoji} {self.created_at.strftime('%Y-%m-%d %H:%M')}: "
            f"{self.tokens} tokens — {self.description or self.usage_type.value}"
        )


@dataclass
class BudgetAlert:
    """Budget alert notification (logged / future inbox)."""

    id: str
    member_id: str
    alert_type: str
    message: str
    sent_at: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False


__all__ = [
    "BudgetAlert",
    "BudgetStatus",
    "MemberBudget",
    "UsageRecord",
    "UsageType",
]
