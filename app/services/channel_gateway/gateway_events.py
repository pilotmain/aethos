# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""In-memory outbound health signals for channel admin (Phase 12 — no DB)."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any

from sqlalchemy.orm import Session

_lock = Lock()
_health: dict[str, dict[str, str]] = {}


def record_outbound_success(channel: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        h = _health.setdefault(channel, {})
        h["last_success"] = now
        h["last_event_at"] = now
        h.pop("last_error", None)


def record_outbound_failure(channel: str, error: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    err = (error or "")[:500]
    with _lock:
        h = _health.setdefault(channel, {})
        h["last_error"] = err
        h["last_event_at"] = now


def get_health_details(channel: str) -> dict[str, str] | None:
    """Subset suitable for ``/api/v1/channels/status`` ``health_details``."""
    with _lock:
        h = _health.get(channel)
        if not h:
            return None
        keys = ("last_event_at", "last_error", "last_success")
        out: dict[str, str] = {k: h[k] for k in keys if k in h and h[k]}
        return out or None


def reset_health_for_tests() -> None:
    with _lock:
        _health.clear()


def audit_outbound_failure(
    db: Session,
    *,
    channel: str,
    user_id: str | None,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Best-effort audit row for Trust Activity when outbound ultimately fails."""
    try:
        from app.services.audit_service import audit

        md = dict(metadata or {})
        md["channel"] = channel
        audit(
            db,
            event_type="gateway.outbound_failed",
            actor="channel_gateway",
            user_id=user_id,
            message=(message or "")[:4000],
            metadata=md,
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception("gateway outbound failure audit skipped")
