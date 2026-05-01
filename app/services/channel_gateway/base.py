from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.orm import Session


class ChannelAdapter(ABC):
    """Shared contract for bringing channel-specific updates into Nexa core."""

    channel: str = ""

    @abstractmethod
    def resolve_app_user_id(self, db: Session, raw_event: Any) -> str:
        """Map channel identity to Nexa `app_user_id` (e.g. link / upsert)."""

    @abstractmethod
    def normalize_message(self, raw_event: Any, *, app_user_id: str) -> dict[str, Any]:
        """Canonical inbound fields for routing, audit, and future gateway use."""

    def verify_signature(self, request: Any) -> bool:
        """HTTP-style channels verify webhooks; Telegram polling has no signature."""
        return True
