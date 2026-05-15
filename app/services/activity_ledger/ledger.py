# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Append-only activity ledger with verifiable hash chain (SQLite-backed)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.openclaw_store import NexaActivityLedgerEvent
from app.services.activity_ledger.hashing import hash_record
from app.services.activity_ledger.models import LedgerEventDict

_GENESIS = "0" * 64


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _last_hash() -> str:
    db = SessionLocal()
    try:
        row = db.scalars(
            select(NexaActivityLedgerEvent)
            .order_by(NexaActivityLedgerEvent.id.desc())
            .limit(1)
        ).first()
        if row is None:
            return _GENESIS
        return row.record_hash
    finally:
        db.close()


def append_event(
    *,
    event_type: str,
    actor: str,
    resource: str,
    payload_summary: dict[str, Any] | None = None,
) -> LedgerEventDict:
    prev = _last_hash()
    body: dict[str, Any] = {
        "event_type": event_type[:120],
        "actor": actor[:120],
        "resource": resource[:2000],
        "payload_summary": dict(payload_summary or {}),
        "previous_hash": prev,
    }
    h = hash_record(prev, body)
    body["hash"] = h

    db = SessionLocal()
    try:
        row = NexaActivityLedgerEvent(
            event_type=body["event_type"],
            actor=body["actor"],
            resource=body["resource"],
            payload_summary=body["payload_summary"],
            previous_hash=prev,
            record_hash=h,
            created_at=_utc_now(),
        )
        db.add(row)
        db.commit()
    finally:
        db.close()

    row_out: LedgerEventDict = body  # type: ignore[assignment]
    return row_out


def chain_hash() -> str:
    return _last_hash()


def events_snapshot() -> list[LedgerEventDict]:
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(NexaActivityLedgerEvent).order_by(NexaActivityLedgerEvent.id.asc())
        ).all()
        return [
            {
                "event_type": r.event_type,
                "actor": r.actor,
                "resource": r.resource,
                "payload_summary": dict(r.payload_summary or {}),
                "previous_hash": r.previous_hash,
                "hash": r.record_hash,
            }
            for r in rows
        ]
    finally:
        db.close()


def verify_chain_integrity() -> bool:
    prev = _GENESIS
    for ev in events_snapshot():
        ph = ev.get("previous_hash") or ""
        if ph != prev:
            return False
        body = {k: v for k, v in ev.items() if k != "hash"}
        expected = hash_record(prev, body)
        if ev.get("hash") != expected:
            return False
        prev = expected
    return True


def reset_chain_for_tests() -> None:
    db = SessionLocal()
    try:
        for row in db.scalars(select(NexaActivityLedgerEvent)).all():
            db.delete(row)
        db.commit()
    finally:
        db.close()


__all__ = [
    "append_event",
    "chain_hash",
    "events_snapshot",
    "reset_chain_for_tests",
    "verify_chain_integrity",
]
