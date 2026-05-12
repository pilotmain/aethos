# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Gateway-level event helpers — publish/list/subscribe will wrap the durable event bus (Phase 6)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def publish_gateway_event(kind: str, payload: dict[str, Any], *, user_id: str | None = None) -> None:
    """Stub publisher; replaces with ``event bus`` + persistence."""
    logger.debug("gateway_event kind=%s user_id=%s keys=%s", kind, user_id, list(payload.keys())[:12])


def list_recent_gateway_events(*, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Stub reader — returns empty until event store exists."""
    _ = (user_id, limit)
    return []
