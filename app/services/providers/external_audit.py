# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Persist outbound provider attempts for audit (Phase 10)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.db import SessionLocal


def persist_external_call(
    db: Session | None,
    *,
    provider: str,
    agent: str,
    mission_id: str | None,
    user_id: str | None,
    redactions: list[dict[str, Any]],
    blocked: bool,
    error: str | None,
) -> None:
    from app.models.nexa_next_runtime import NexaExternalCall

    row = NexaExternalCall(
        provider=provider[:64],
        agent=(agent or "")[:128],
        mission_id=mission_id[:64] if mission_id else None,
        user_id=user_id[:64] if user_id else None,
        redactions=list(redactions),
        blocked=blocked,
        error=(error or "")[:2000] if error else None,
    )
    session = db if db is not None else SessionLocal()
    close_it = db is None
    try:
        session.add(row)
        session.commit()
    finally:
        if close_it:
            session.close()


__all__ = ["persist_external_call"]
