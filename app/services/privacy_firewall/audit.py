"""Audit hooks for privacy decisions (ties into ``audit_logs`` / trust stream)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

LOG: list[dict[str, Any]] = []


def log_event(event: dict[str, Any]) -> None:
    LOG.append(event)


def log_privacy_decision(event_type: str, *, user_id: str | None, detail: dict[str, Any]) -> None:
    """Emit structured log; DB audit wiring comes in Phase 10."""
    logger.info(
        "privacy_audit event=%s user_prefix=%s keys=%s",
        event_type,
        (user_id or "")[:24],
        list(detail.keys())[:16],
    )
