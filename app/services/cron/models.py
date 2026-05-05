"""Data models for Nexa cron jobs (Phase 13)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class JobActionType(str, Enum):
    SKILL = "skill"
    HOST_ACTION = "host_action"
    CHANNEL_MESSAGE = "channel_message"
    CHAIN = "chain"
    WEBHOOK = "webhook"


@dataclass
class CronJob:
    """Scheduled cron job."""

    id: str
    name: str
    cron_expression: str
    action_type: JobActionType
    action_payload: dict[str, Any]
    status: JobStatus = JobStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_error: str | None = None
    run_count: int = 0
    created_by: str | None = None
    created_by_channel: str | None = None
    timezone: str = "UTC"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "cron_expression": self.cron_expression,
            "action_type": self.action_type.value,
            "action_payload": self.action_payload,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "last_error": self.last_error,
            "run_count": self.run_count,
            "created_by": self.created_by,
            "created_by_channel": self.created_by_channel,
            "timezone": self.timezone,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CronJob:
        return cls(
            id=data["id"],
            name=data["name"],
            cron_expression=data["cron_expression"],
            action_type=JobActionType(data["action_type"]),
            action_payload=dict(data.get("action_payload") or {}),
            status=JobStatus(data.get("status", "active")),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
            last_run_at=datetime.fromisoformat(data["last_run_at"]) if data.get("last_run_at") else None,
            next_run_at=datetime.fromisoformat(data["next_run_at"]) if data.get("next_run_at") else None,
            last_error=data.get("last_error"),
            run_count=int(data.get("run_count") or 0),
            created_by=data.get("created_by"),
            created_by_channel=data.get("created_by_channel"),
            timezone=data.get("timezone") or "UTC",
        )


__all__ = ["CronJob", "JobActionType", "JobStatus"]
