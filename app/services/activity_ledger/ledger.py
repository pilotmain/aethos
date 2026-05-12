# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Append-only in-memory activity ledger with verifiable hash chain."""

from __future__ import annotations

from typing import Any

from app.services.activity_ledger.hashing import hash_record
from app.services.activity_ledger.models import LedgerEventDict

_GENESIS = "0" * 64

_CHAIN: list[LedgerEventDict] = []
_LAST_HASH: str = _GENESIS


def append_event(
    *,
    event_type: str,
    actor: str,
    resource: str,
    payload_summary: dict[str, Any] | None = None,
) -> LedgerEventDict:
    global _LAST_HASH
    body: dict[str, Any] = {
        "event_type": event_type[:120],
        "actor": actor[:120],
        "resource": resource[:2000],
        "payload_summary": dict(payload_summary or {}),
        "previous_hash": _LAST_HASH,
    }
    h = hash_record(_LAST_HASH, body)
    body["hash"] = h
    row: LedgerEventDict = body  # type: ignore[assignment]
    _CHAIN.append(row)
    _LAST_HASH = h
    return row


def chain_hash() -> str:
    return _LAST_HASH


def events_snapshot() -> list[LedgerEventDict]:
    return list(_CHAIN)


def verify_chain_integrity() -> bool:
    prev = _GENESIS
    for ev in _CHAIN:
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
    global _LAST_HASH, _CHAIN
    _CHAIN = []
    _LAST_HASH = _GENESIS


__all__ = [
    "append_event",
    "chain_hash",
    "events_snapshot",
    "reset_chain_for_tests",
    "verify_chain_integrity",
]
