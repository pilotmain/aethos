"""Audit trail for access denials (no long message bodies, no secrets)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.audit_service import audit
from app.services.trust_audit_constants import ACCESS_SURFACE_DENIED_LEGACY

logger = logging.getLogger(__name__)

_MAX_PRE = 80


def log_access_denied(
    db: Session,
    *,
    app_user_id: str | None,
    telegram_id: int,
    username: str | None,
    command_family: str,
    reason: str,
    preview: str | None = None,
) -> None:
    p = (preview or "").replace("\n", " ").strip()[:_MAX_PRE]
    meta: dict[str, Any] = {
        "allowed": False,
        "command_family": (command_family or "unknown")[:64],
        "reason": (reason or "")[:200],
        "username": (username or "")[:64] if username else None,
    }
    if p:
        meta["preview_sanitized"] = p
    try:
        audit(
            db,
            event_type=ACCESS_SURFACE_DENIED_LEGACY,
            actor="telegram",
            user_id=app_user_id,
            job_id=None,
            message=(f"tg:{telegram_id} {command_family} {reason} {p}").strip()[:2000],
            metadata=meta,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("access audit failed: %s", e)
